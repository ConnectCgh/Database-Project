import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from Project.db_utils import (
    execute_fetchall,
    execute_fetchone,
    execute_non_query,
    execute_write,
    get_customer_by_user,
    quote_table,
)


MEAL_TYPE_DISPLAY = {
    'breakfast': '早餐',
    'lunch': '午餐',
    'dinner': '晚餐',
    'lunch_and_dinner': '午餐和晚餐',
}

ORDER_STATUS_DISPLAY = {
    'unassigned': '未分配骑手',
    'assigned': '已分配骑手',
    'ready': '顾客待取餐',
    'completed': '已完成',
    'cancelled': '已取消',
}

PLATFORM_TABLE = quote_table('platform')
ORDER_TABLE = quote_table('order')
ORDER_RATING_TABLE = quote_table('order_rating')
ORDER_ITEM_TABLE = quote_table('order_item')
ORDER_MEAL_RATING_TABLE = quote_table('order_meal_rating')
MERCHANT_TABLE = quote_table('merchant')
MEAL_TABLE = quote_table('meal')
RIDER_TABLE = quote_table('rider')


def _format_decimal(value):
    if value is None:
        return '0.00'
    return str(Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _normalize_rating(value):
    if value is None or value == '':
        raise ValueError('评分不能为空')
    rating = Decimal(str(value))
    if rating < Decimal('0') or rating > Decimal('5'):
        raise ValueError('评分必须在0到5之间')
    return rating.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _update_entity_rating(table_name, entity_id, rating_value):
    if not entity_id:
        return
    query = f'''
        UPDATE {table_name}
        SET rating_score = ROUND(((rating_score * rating_count) + %s) / (rating_count + 1), 2),
            rating_count = rating_count + 1
        WHERE id = %s
    '''
    execute_non_query(query, [rating_value, entity_id])


def _get_platforms():
    query = f'''
        SELECT id, platform_name, phone, rating_score, rating_count
        FROM {PLATFORM_TABLE}
        ORDER BY platform_name
    '''
    return execute_fetchall(query)


def _get_all_merchants():
    query = f'''
        SELECT id, merchant_name, phone, address, rating_score, rating_count
        FROM {MERCHANT_TABLE}
        ORDER BY merchant_name
    '''
    return execute_fetchall(query)


def _get_platforms_for_merchant(merchant_id):
    query = f'''
        SELECT p.id AS platform_id,
               p.platform_name,
               p.phone,
               p.rating_score,
               p.rating_count
        FROM enter_request er
        JOIN {PLATFORM_TABLE} p ON er.platform_id = p.id
        WHERE er.merchant_id = %s AND er.status = 'approved'
        ORDER BY p.platform_name
    '''
    return execute_fetchall(query, [merchant_id])


def _get_meals_for_merchant_platform(merchant_id, platform_id):
    query = '''
        SELECT id, name, price, meal_type, created_at, rating_score, rating_count
        FROM meal
        WHERE merchant_id = %s AND platform_id = %s
        ORDER BY created_at DESC
    '''
    meals = execute_fetchall(query, [merchant_id, platform_id])
    for meal in meals:
        meal['get_meal_type_display'] = MEAL_TYPE_DISPLAY.get(meal['meal_type'], meal['meal_type'])
        meal['rating_score'] = _format_decimal(meal['rating_score'])
        meal['rating_count'] = meal['rating_count']
    return meals


def _get_customer(order_user):
    customer = get_customer_by_user(order_user.id)
    if not customer:
        raise ValueError('Customer does not exist')
    return customer


def _get_customer_order_rows(customer_id):
    base_query = f'''
        SELECT o.id,
               o.price,
               o.status,
               o.created_at,
               o.merchant_id,
               o.platform_id,
               o.rider_id,
               m.merchant_name,
               p.platform_name,
               d.id AS discount_id,
               d.discount_rate,
               r.rider_name,
               rating.id AS rating_id,
               rating.merchant_rating,
               rating.platform_rating,
               rating.rider_rating
        FROM {ORDER_TABLE} o
        JOIN merchant m ON o.merchant_id = m.id
        JOIN {PLATFORM_TABLE} p ON o.platform_id = p.id
        LEFT JOIN discount d ON o.discount_id = d.id
        LEFT JOIN rider r ON o.rider_id = r.id
        LEFT JOIN {ORDER_RATING_TABLE} rating ON rating.order_id = o.id
        WHERE o.customer_id = %s
        ORDER BY o.created_at DESC
    '''
    orders = execute_fetchall(base_query, [customer_id])
    if not orders:
        return []

    order_map = {order['id']: order for order in orders}
    for order in order_map.values():
        order['meals'] = []

    order_ids = list(order_map.keys())
    placeholders = _build_in_clause(order_ids)

    items_query = f'''
        SELECT oi.id,
               oi.order_id,
               oi.meal_id,
               meal.name AS meal_name,
               oi.quantity,
               oi.unit_price,
               oi.line_price
        FROM {ORDER_ITEM_TABLE} oi
        JOIN meal ON oi.meal_id = meal.id
        WHERE oi.order_id IN ({placeholders})
        ORDER BY oi.id
    '''
    items = execute_fetchall(items_query, order_ids)
    item_lookup = {}
    for item in items:
        entry = {
            'item_id': item['id'],
            'meal_id': item['meal_id'],
            'meal_name': item['meal_name'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'line_price': item['line_price'],
            'rating': None,
        }
        order_map[item['order_id']]['meals'].append(entry)
        item_lookup[item['id']] = entry

    ratings_query = f'''
        SELECT omr.order_id,
               omr.order_item_id,
               omr.rating
        FROM {ORDER_MEAL_RATING_TABLE} omr
        WHERE omr.order_id IN ({placeholders})
    '''
    meal_ratings = execute_fetchall(ratings_query, order_ids)
    for rating in meal_ratings:
        item_entry = item_lookup.get(rating['order_item_id'])
        if item_entry is not None:
            item_entry['rating'] = _format_decimal(rating['rating'])

    return orders


def _extract_order_rating(row):
    if not row['rating_id']:
        return None
    return {
        'merchant': _format_decimal(row['merchant_rating']),
        'platform': _format_decimal(row['platform_rating']),
        'rider': _format_decimal(row['rider_rating']) if row['rider_rating'] is not None else None,
    }


def _format_meal_summary(meals):
    if not meals:
        return ''
    return ', '.join(f"{meal['name']} x{meal['quantity']}" for meal in meals)


def _build_order_context(order_rows):
    result = []
    for row in order_rows:
        order_rating = _extract_order_rating(row)
        meals = []
        for meal in row.get('meals', []):
            meals.append({
                'id': meal['item_id'],
                'name': meal['meal_name'],
                'quantity': meal['quantity'],
                'unit_price': meal['unit_price'],
                'line_price': meal['line_price'],
                'rating': meal['rating'],
            })
        result.append({
            'id': row['id'],
            'price': row['price'],
            'status': row['status'],
            'get_status_display': ORDER_STATUS_DISPLAY.get(row['status'], row['status']),
            'created_at': row['created_at'],
            'merchant': {'merchant_name': row['merchant_name']},
            'platform': {'platform_name': row['platform_name']},
            'meals': meals,
            'meal_summary': _format_meal_summary(meals),
            'discount': {'discount_rate': row['discount_rate']} if row['discount_id'] else None,
            'rider': {'rider_name': row['rider_name']} if row['rider_name'] else None,
            'rating': order_rating,
            'can_rate': row['status'] == 'completed' and order_rating is None,
        })
    return result


def _build_order_payload(order_rows):
    result = []
    for row in order_rows:
        order_rating = _extract_order_rating(row)
        meals_payload = []
        for meal in row.get('meals', []):
            meals_payload.append({
                'id': meal['item_id'],
                'meal_id': meal['meal_id'],
                'name': meal['meal_name'],
                'quantity': meal['quantity'],
                'unit_price': str(meal['unit_price']),
                'line_price': str(meal['line_price']),
                'rating': meal['rating'],
            })
        result.append({
            'id': row['id'],
            'merchant_name': row['merchant_name'],
            'platform_name': row['platform_name'],
            'price': str(row['price']),
            'discount_id': row['discount_id'],
            'discount_rate': str(row['discount_rate'] * 100) if row['discount_id'] else '0',
            'rider_name': row['rider_name'],
            'status': row['status'],
             'status_display': ORDER_STATUS_DISPLAY.get(row['status'], row['status']),
            'can_rate': row['status'] == 'completed' and order_rating is None,
            'has_rating': order_rating is not None,
            'rating': order_rating,
            'merchant_id': row['merchant_id'],
            'platform_id': row['platform_id'],
            'rider_id': row['rider_id'],
            'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
            'meals': meals_payload,
            'meal_summary': _format_meal_summary(meals_payload),
        })
    return result


def _get_enter_request(merchant_id, platform_id):
    query = f'''
        SELECT er.id,
               m.id AS merchant_id,
               m.merchant_name,
               m.phone AS merchant_phone,
               m.address AS merchant_address,
               m.rating_score AS merchant_rating_score,
               m.rating_count AS merchant_rating_count,
               p.id AS platform_id,
               p.platform_name,
               p.rating_score AS platform_rating_score,
               p.rating_count AS platform_rating_count
        FROM enter_request er
        JOIN merchant m ON er.merchant_id = m.id
        JOIN {PLATFORM_TABLE} p ON er.platform_id = p.id
        WHERE er.merchant_id = %s AND er.platform_id = %s AND er.status = 'approved'
    '''
    return execute_fetchone(query, [merchant_id, platform_id])


def _get_available_discounts(merchant_id, platform_id):
    query = '''
        SELECT d.id, d.discount_rate
        FROM merchant_platform_discount mpd
        JOIN discount d ON mpd.discount_id = d.id
        WHERE mpd.merchant_id = %s AND mpd.platform_id = %s
        ORDER BY d.discount_rate
    '''
    return execute_fetchall(query, [merchant_id, platform_id])


def _get_discount_for_order(merchant_id, platform_id, discount_id):
    query = '''
        SELECT d.id, d.discount_rate
        FROM merchant_platform_discount mpd
        JOIN discount d ON mpd.discount_id = d.id
        WHERE mpd.merchant_id = %s AND mpd.platform_id = %s AND d.id = %s
    '''
    return execute_fetchone(query, [merchant_id, platform_id, discount_id])


def _fetch_meal(merchant_id, platform_id, meal_id):
    query = '''
        SELECT id, name, price
        FROM meal
        WHERE id = %s AND merchant_id = %s AND platform_id = %s
    '''
    return execute_fetchone(query, [meal_id, merchant_id, platform_id])


def _get_available_meal_ids(merchant_id, platform_id):
    query = 'SELECT id FROM meal WHERE merchant_id = %s AND platform_id = %s'
    rows = execute_fetchall(query, [merchant_id, platform_id])
    return [row['id'] for row in rows]


def _build_in_clause(values):
    return ','.join(['%s'] * len(values))


def _meal_type_filters(meal_type):
    if meal_type == 'breakfast':
        return ['breakfast']
    if meal_type == 'lunch':
        return ['lunch', 'lunch_and_dinner']
    if meal_type == 'dinner':
        return ['dinner', 'lunch_and_dinner']
    if meal_type == 'lunch_and_dinner':
        return ['lunch', 'dinner', 'lunch_and_dinner']
    return []


@login_required
def customer(request):
    try:
        current_customer = _get_customer(request.user)
        customer_name = current_customer['customer_name']

        platforms = _get_platforms()
        for platform in platforms:
            platform['rating_score'] = _format_decimal(platform['rating_score'])
        merchants = _get_all_merchants()

        merchants_with_platforms = []
        for merchant in merchants:
            merchant['rating_score'] = _format_decimal(merchant['rating_score'])
            approved_platforms = _get_platforms_for_merchant(merchant['id'])
            if not approved_platforms:
                continue

            total_platforms = []
            platforms_with_meals = []
            for platform in approved_platforms:
                platform_info = {
                    'id': platform['platform_id'],
                    'platform_name': platform['platform_name'],
                    'rating_score': _format_decimal(platform['rating_score']),
                    'rating_count': platform['rating_count'],
                }
                meals = _get_meals_for_merchant_platform(merchant['id'], platform['platform_id'])
                platforms_with_meals.append({
                    'platform': platform_info,
                    'meals': meals,
                    'meals_count': len(meals),
                })
                total_platforms.append(platform_info)

            merchants_with_platforms.append({
                'merchant': merchant,
                'platforms': total_platforms,
                'platforms_with_meals': platforms_with_meals,
            })

        discounts = execute_fetchall('SELECT id, discount_rate FROM discount ORDER BY discount_rate')
        orders = _build_order_context(_get_customer_order_rows(current_customer['id']))

    except ValueError:
        customer_name = request.user.username
        platforms = []
        merchants_with_platforms = []
        discounts = []
        orders = []
        current_customer = None

    context = {
        'customer_name': customer_name,
        'platforms': platforms,
        'merchants_with_platforms': merchants_with_platforms,
        'discounts': discounts,
        'orders': orders,
        'customer': current_customer,
    }

    return render(request, 'customer.html', context)


@login_required
def get_merchant_detail(request, merchant_id, platform_id):
    try:
        enter_request = _get_enter_request(merchant_id, platform_id)
        if not enter_request:
            raise ValueError('商家未入驻该平台')

        meals = _get_meals_for_merchant_platform(merchant_id, platform_id)
        available_discounts = []
        for discount in _get_available_discounts(merchant_id, platform_id):
            rate = Decimal(discount['discount_rate'])
            discount_display = f"{(Decimal('1') - rate) * Decimal('10'):.0f}折"
            available_discounts.append({
                'id': discount['id'],
                'discount_rate': str(rate),
                'discount_display': discount_display,
            })

        return JsonResponse({
            'success': True,
            'merchant': {
                'id': enter_request['merchant_id'],
                'merchant_name': enter_request['merchant_name'],
                'phone': enter_request['merchant_phone'],
                'address': enter_request['merchant_address'],
                'rating_score': _format_decimal(enter_request['merchant_rating_score']),
                'rating_count': enter_request['merchant_rating_count'],
            },
            'platform': {
                'id': enter_request['platform_id'],
                'platform_name': enter_request['platform_name'],
                'rating_score': _format_decimal(enter_request['platform_rating_score']),
                'rating_count': enter_request['platform_rating_count'],
            },
            'meals': [{
                'id': meal['id'],
                'name': meal['name'],
                'price': str(meal['price']),
                'meal_type': meal['meal_type'],
                'created_at': meal['created_at'].strftime('%Y-%m-%d %H:%M') if meal['created_at'] else '',
                'rating_score': meal['rating_score'],
                'rating_count': meal['rating_count'],
            } for meal in meals],
            'available_discounts': available_discounts,
        })
    except Exception as exc:
        return JsonResponse({
            'success': False,
            'message': f'获取商家详情失败: {str(exc)}',
        })


@login_required
@csrf_exempt
def place_order(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        current_customer = _get_customer(request.user)
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        platform_id = data.get('platform_id')
        meals_data = data.get('meals', [])
        discount_id = data.get('discount_id')
        total_price = data.get('total_price')

        if not all([merchant_id, platform_id, meals_data]) or total_price is None:
            return JsonResponse({'success': False, 'message': '缺少必要的订单信息'})

        enter_request = _get_enter_request(merchant_id, platform_id)
        if not enter_request:
            return JsonResponse({'success': False, 'message': '商家未入驻该平台或入驻申请未通过'})

        discount = None
        if discount_id and discount_id not in ['', 'null']:
            discount = _get_discount_for_order(merchant_id, platform_id, discount_id)
            if not discount:
                discount = None

        order_items = []
        total_price_decimal = Decimal('0')
        for meal_data in meals_data:
            meal_id = meal_data.get('meal_id')
            quantity = int(meal_data.get('quantity', 1))
            if quantity < 1:
                quantity = 1
            meal = _fetch_meal(merchant_id, platform_id, meal_id)
            if not meal:
                available_ids = _get_available_meal_ids(merchant_id, platform_id)
                return JsonResponse({
                    'success': False,
                    'message': f'餐品不存在或不属于该商家和平台。餐品ID: {meal_id}, 可用餐品: {available_ids}',
                })

            unit_price = Decimal(meal['price'])
            line_price = unit_price * Decimal(quantity)
            if discount:
                line_price = line_price * (Decimal('1') - Decimal(discount['discount_rate']))
            line_price = line_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            order_items.append({
                'meal_id': meal['id'],
                'meal_name': meal['name'],
                'quantity': quantity,
                'unit_price': unit_price,
                'line_price': line_price,
            })
            total_price_decimal += line_price

        total_price_decimal = total_price_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        with transaction.atomic():
            order_query = f'''
                INSERT INTO {ORDER_TABLE} (customer_id, platform_id, merchant_id, discount_id, rider_id, price, status, created_at)
                VALUES (%s, %s, %s, %s, NULL, %s, 'unassigned', CURRENT_TIMESTAMP)
            '''
            order_id = execute_write(order_query, [
                current_customer['id'],
                platform_id,
                merchant_id,
                discount['id'] if discount else None,
                total_price_decimal,
            ])

            item_query = f'''
                INSERT INTO {ORDER_ITEM_TABLE} (order_id, meal_id, quantity, unit_price, line_price, created_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            '''
            for item in order_items:
                execute_write(item_query, [
                    order_id,
                    item['meal_id'],
                    item['quantity'],
                    item['unit_price'],
                    item['line_price'],
                ])

        order_summary = {
            'id': order_id,
            'meals': [{
                'name': item['meal_name'],
                'quantity': item['quantity'],
                'line_price': str(item['line_price']),
            } for item in order_items],
            'price': str(total_price_decimal),
            'status': 'unassigned',
        }

        return JsonResponse({
            'success': True,
            'message': '下单成功',
            'orders': [order_summary],
            'total_price': str(total_price_decimal),
        })
    except ValueError:
        return JsonResponse({'success': False, 'message': '顾客信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'下单失败: {str(exc)}'})


@login_required
def get_orders(request):
    try:
        current_customer = _get_customer(request.user)
        order_rows = _get_customer_order_rows(current_customer['id'])
        return JsonResponse({'success': True, 'orders': _build_order_payload(order_rows)})
    except ValueError:
        return JsonResponse({'success': False, 'message': '顾客信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'获取订单失败: {str(exc)}'})


@login_required
def search_merchants(request):
    try:
        platform_id = request.GET.get('platform_id')
        merchant_name = request.GET.get('merchant_name')
        meal_name = request.GET.get('meal_name')
        meal_type = request.GET.get('meal_type')

        base_query = '''
            SELECT DISTINCT m.id,
                            m.merchant_name,
                            m.phone,
                            m.address,
                            m.rating_score,
                            m.rating_count
            FROM merchant m
            JOIN enter_request er ON er.merchant_id = m.id
            WHERE er.status = 'approved'
        '''
        conditions = []
        params = []

        if platform_id:
            conditions.append('er.platform_id = %s')
            params.append(platform_id)
        if merchant_name:
            conditions.append('m.merchant_name LIKE %s')
            params.append(f'%{merchant_name}%')

        if conditions:
            base_query += ' AND ' + ' AND '.join(conditions)
        base_query += ' ORDER BY m.merchant_name'

        merchants = execute_fetchall(base_query, params)

        result_data = []
        for merchant in merchants:
            approved_platforms = _get_platforms_for_merchant(merchant['id'])
            platforms_with_meals = []

            for platform in approved_platforms:
                if platform_id and str(platform['platform_id']) != str(platform_id):
                    continue

                meal_query = '''
                    SELECT id, name, price, meal_type, rating_score, rating_count
                    FROM meal
                    WHERE merchant_id = %s AND platform_id = %s
                '''
                meal_params = [merchant['id'], platform['platform_id']]

                if meal_name:
                    meal_query += ' AND name LIKE %s'
                    meal_params.append(f'%{meal_name}%')

                allowed_types = _meal_type_filters(meal_type)
                if allowed_types:
                    placeholders = ','.join(['%s'] * len(allowed_types))
                    meal_query += f' AND meal_type IN ({placeholders})'
                    meal_params.extend(allowed_types)

                meals = execute_fetchall(meal_query + ' ORDER BY name', meal_params)
                for meal in meals:
                    meal['get_meal_type_display'] = MEAL_TYPE_DISPLAY.get(meal['meal_type'], meal['meal_type'])
                    meal['rating_score'] = _format_decimal(meal['rating_score'])
                    meal['rating_count'] = meal['rating_count']

                if meals or (not meal_name and not meal_type):
                    platform_info = {
                        'id': platform['platform_id'],
                        'platform_name': platform['platform_name'],
                        'rating_score': _format_decimal(platform['rating_score']),
                        'rating_count': platform['rating_count'],
                    }
                    platforms_with_meals.append({
                        'platform': platform_info,
                        'meals': meals,
                        'meals_count': len(meals),
                    })

            if platforms_with_meals:
                result_data.append({
                    'merchant': merchant,
                    'platforms_with_meals': platforms_with_meals,
                })

        return JsonResponse({'success': True, 'merchants': result_data})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'搜索失败: {str(exc)}'})


@login_required
@csrf_exempt
def delete_order(request, order_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        current_customer = _get_customer(request.user)
        order_query = f'''
            SELECT id, status
            FROM {ORDER_TABLE}
            WHERE id = %s AND customer_id = %s
        '''
        order = execute_fetchone(order_query, [order_id, current_customer['id']])
        if not order:
            return JsonResponse({'success': False, 'message': '订单不存在或不属于当前顾客'})

        if order['status'] not in ['unassigned', 'cancelled']:
            return JsonResponse({'success': False, 'message': '只能删除未分配骑手或已取消的订单'})

        execute_non_query(f'DELETE FROM {ORDER_TABLE} WHERE id = %s', [order_id])
        return JsonResponse({'success': True, 'message': '订单删除成功'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '顾客信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'删除订单失败: {str(exc)}'})


@login_required
@csrf_exempt
def pickup_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        current_customer = _get_customer(request.user)
        order_query = f'''
            SELECT o.id,
                   o.status,
                   o.price,
                   m.merchant_name
            FROM {ORDER_TABLE} o
            JOIN merchant m ON o.merchant_id = m.id
            WHERE o.id = %s AND o.customer_id = %s
        '''
        order = execute_fetchone(order_query, [order_id, current_customer['id']])
        if not order:
            return JsonResponse({'success': False, 'message': '订单不存在或不属于当前顾客'})

        if order['status'] != 'ready':
            return JsonResponse({'success': False, 'message': '只能取餐状态为"待取餐"的订单'})

        update_query = f'''
            UPDATE {ORDER_TABLE}
            SET status = 'completed'
            WHERE id = %s
        '''
        execute_non_query(update_query, [order_id])
        meal_rows = execute_fetchall(
            f'''
            SELECT meal.name, oi.quantity
            FROM {ORDER_ITEM_TABLE} oi
            JOIN meal ON oi.meal_id = meal.id
            WHERE oi.order_id = %s
            ORDER BY oi.id
            ''',
            [order_id],
        )
        meal_summary = ', '.join(f"{row['name']}x{row['quantity']}" for row in meal_rows) if meal_rows else ''
        order_info = {
            'id': order['id'],
            'customer': current_customer['customer_name'],
            'merchant': order['merchant_name'],
            'meals': meal_summary,
            'price': str(order['price']),
            'status': 'completed',
        }
        return JsonResponse({
            'success': True,
            'message': '取餐成功，订单已完成，请为本次体验评分',
            'order_info': order_info,
        })
    except ValueError:
        return JsonResponse({'success': False, 'message': '顾客信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'取餐失败: {str(exc)}'})


@login_required
@csrf_exempt
def rate_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        current_customer = _get_customer(request.user)
        data = json.loads(request.body)
        merchant_rating = _normalize_rating(data.get('merchant_rating'))
        platform_rating = _normalize_rating(data.get('platform_rating'))
        rider_rating_value = data.get('rider_rating')
        rider_rating = _normalize_rating(rider_rating_value) if rider_rating_value not in [None, ''] else None
        meal_ratings_payload = data.get('meal_ratings', [])

        order = execute_fetchone(
            f'''
            SELECT o.id, o.merchant_id, o.platform_id, o.rider_id, o.status
            FROM {ORDER_TABLE} o
            WHERE o.id = %s AND o.customer_id = %s
            ''',
            [order_id, current_customer['id']],
        )
        if not order:
            return JsonResponse({'success': False, 'message': '订单不存在或不属于当前顾客'})
        if order['status'] != 'completed':
            return JsonResponse({'success': False, 'message': '仅已完成的订单可以评价'})

        existing_rating = execute_fetchone(f'SELECT id FROM {ORDER_RATING_TABLE} WHERE order_id = %s', [order_id])
        if existing_rating:
            return JsonResponse({'success': False, 'message': '订单已评价'})

        if order['rider_id'] and rider_rating is None:
            return JsonResponse({'success': False, 'message': '请为骑手评分'})
        if not order['rider_id']:
            rider_rating = None

        order_items = execute_fetchall(
            f'''
            SELECT oi.id, oi.meal_id, meal.name AS meal_name
            FROM {ORDER_ITEM_TABLE} oi
            JOIN meal ON oi.meal_id = meal.id
            WHERE oi.order_id = %s
            ORDER BY oi.id
            ''',
            [order_id],
        )
        if not order_items:
            return JsonResponse({'success': False, 'message': '订单中没有餐品，无法评价'})

        if len(meal_ratings_payload) != len(order_items):
            return JsonResponse({'success': False, 'message': '请为订单中的每个餐品评分'})

        order_item_ids = {item['id'] for item in order_items}
        normalized_meal_ratings = {}
        for rating_entry in meal_ratings_payload:
            item_id = rating_entry.get('order_item_id')
            if item_id is None:
                return JsonResponse({'success': False, 'message': '缺少餐品评分信息'})
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'message': '餐品评分数据无效'})
            if item_id not in order_item_ids:
                return JsonResponse({'success': False, 'message': '餐品评分与订单不匹配'})
            if item_id in normalized_meal_ratings:
                return JsonResponse({'success': False, 'message': '同一餐品不能重复评分'})
            normalized_meal_ratings[item_id] = _normalize_rating(rating_entry.get('rating'))

        missing_items = order_item_ids - set(normalized_meal_ratings.keys())
        if missing_items:
            return JsonResponse({'success': False, 'message': '请为订单中的每个餐品评分'})

        with transaction.atomic():
            execute_write(
                f'''
                INSERT INTO {ORDER_RATING_TABLE} (order_id, merchant_rating, platform_rating, rider_rating, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ''',
                [order_id, merchant_rating, platform_rating, rider_rating],
            )

            insert_meal_rating_query = f'''
                INSERT INTO {ORDER_MEAL_RATING_TABLE} (order_id, order_item_id, meal_id, rating, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            '''
            for item in order_items:
                rating_value = normalized_meal_ratings[item['id']]
                execute_write(insert_meal_rating_query, [order_id, item['id'], item['meal_id'], rating_value])

        _update_entity_rating(MERCHANT_TABLE, order['merchant_id'], merchant_rating)
        _update_entity_rating(PLATFORM_TABLE, order['platform_id'], platform_rating)
        if order['rider_id'] and rider_rating is not None:
            _update_entity_rating(RIDER_TABLE, order['rider_id'], rider_rating)
        for item in order_items:
            _update_entity_rating(MEAL_TABLE, item['meal_id'], normalized_meal_ratings[item['id']])

        rating_payload = {
            'merchant': _format_decimal(merchant_rating),
            'platform': _format_decimal(platform_rating),
            'rider': _format_decimal(rider_rating) if rider_rating is not None else None,
            'meals': [{
                'order_item_id': item['id'],
                'meal_name': item['meal_name'],
                'rating': _format_decimal(normalized_meal_ratings[item['id']]),
            } for item in order_items],
        }

        return JsonResponse({'success': True, 'message': '感谢您的评价！', 'rating': rating_payload})
    except (ValueError, InvalidOperation) as exc:
        return JsonResponse({'success': False, 'message': str(exc)})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'评价失败: {str(exc)}'})
