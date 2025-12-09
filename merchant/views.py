from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from Project.db_utils import (
    execute_fetchall,
    execute_fetchone,
    execute_non_query,
    execute_write,
    get_merchant_by_user,
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


def _get_merchant(user):
    merchant = get_merchant_by_user(user.id)
    if not merchant:
        raise ValueError('商家信息不存在')
    return merchant


def _get_platform(platform_id):
    query = f'SELECT id, platform_name, phone FROM {PLATFORM_TABLE} WHERE id = %s'
    return execute_fetchone(query, [platform_id])


def _get_platforms_by_status(merchant_id, status):
    query = f'''
        SELECT p.id, p.platform_name, p.phone
        FROM enter_request er
        JOIN {PLATFORM_TABLE} p ON er.platform_id = p.id
        WHERE er.merchant_id = %s AND er.status = %s
        ORDER BY p.platform_name
    '''
    return execute_fetchall(query, [merchant_id, status])


def _merchant_joined_platform(merchant_id, platform_id):
    query = '''
        SELECT id
        FROM enter_request
        WHERE merchant_id = %s AND platform_id = %s AND status = 'approved'
    '''
    return execute_fetchone(query, [merchant_id, platform_id]) is not None


def _get_meal(merchant_id, meal_id):
    query = '''
        SELECT id, name, price, meal_type, platform_id
        FROM meal
        WHERE id = %s AND merchant_id = %s
    '''
    return execute_fetchone(query, [meal_id, merchant_id])


def _format_meals_for_context(meals):
    formatted = []
    for meal in meals:
        formatted.append({
            'id': meal['id'],
            'name': meal['name'],
            'price': meal['price'],
            'meal_type': meal['meal_type'],
            'get_meal_type_display': MEAL_TYPE_DISPLAY.get(meal['meal_type'], meal['meal_type']),
            'platform': {
                'id': meal['platform_id'],
                'platform_name': meal['platform_name'],
            },
            'created_at': meal['created_at'],
        })
    return formatted


def _get_meals_for_merchant(merchant_id):
    query = f'''
        SELECT meal.id,
               meal.name,
               meal.price,
               meal.meal_type,
               meal.created_at,
               p.id AS platform_id,
               p.platform_name
        FROM meal
        JOIN {PLATFORM_TABLE} p ON meal.platform_id = p.id
        WHERE meal.merchant_id = %s
        ORDER BY meal.created_at DESC
    '''
    return execute_fetchall(query, [merchant_id])


def _get_discounts_for_merchant(merchant_id):
    query = f'''
        SELECT mpd.id,
               mpd.updated_at,
               p.id AS platform_id,
               p.platform_name,
               d.id AS discount_id,
               d.discount_rate
        FROM merchant_platform_discount mpd
        JOIN {PLATFORM_TABLE} p ON mpd.platform_id = p.id
        JOIN discount d ON mpd.discount_id = d.id
        WHERE mpd.merchant_id = %s
        ORDER BY mpd.updated_at DESC
    '''
    rows = execute_fetchall(query, [merchant_id])
    formatted = []
    for row in rows:
        formatted.append({
            'id': row['id'],
            'platform': {
                'id': row['platform_id'],
                'platform_name': row['platform_name'],
            },
            'discount': {
                'id': row['discount_id'],
                'discount_rate': row['discount_rate'],
            },
            'updated_at': row['updated_at'],
        })
    return formatted


def _get_available_discounts():
    return execute_fetchall('SELECT id, discount_rate FROM discount ORDER BY discount_rate')


def _get_orders_for_merchant(merchant_id):
    query = f'''
        SELECT o.id,
               o.price,
               o.status,
               o.created_at,
               c.customer_name,
               p.platform_name,
               meal.name AS meal_name,
               r.rider_name,
               d.id AS discount_id,
               d.discount_rate
        FROM {ORDER_TABLE} o
        JOIN customer c ON o.customer_id = c.id
        JOIN {PLATFORM_TABLE} p ON o.platform_id = p.id
        JOIN meal ON o.meal_id = meal.id
        LEFT JOIN rider r ON o.rider_id = r.id
        LEFT JOIN discount d ON o.discount_id = d.id
        WHERE o.merchant_id = %s
        ORDER BY o.created_at DESC
    '''
    return execute_fetchall(query, [merchant_id])


def _format_orders_for_context(order_rows):
    formatted = []
    for row in order_rows:
        formatted.append({
            'id': row['id'],
            'price': row['price'],
            'status': row['status'],
            'get_status_display': ORDER_STATUS_DISPLAY.get(row['status'], row['status']),
            'created_at': row['created_at'],
            'customer': {'customer_name': row['customer_name']},
            'platform': {'platform_name': row['platform_name']},
            'meal': {'name': row['meal_name']},
            'rider': {'rider_name': row['rider_name']} if row['rider_name'] else None,
            'discount': {'discount_rate': row['discount_rate']} if row['discount_id'] else None,
        })
    return formatted


def _format_orders_for_payload(order_rows):
    formatted = []
    for row in order_rows:
        formatted.append({
            'id': row['id'],
            'customer_name': row['customer_name'],
            'platform_name': row['platform_name'],
            'meal_name': row['meal_name'],
            'price': str(row['price']),
            'rider_name': row['rider_name'],
            'status': row['status'],
            'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M') if row['created_at'] else '',
            'discount_rate': str(row['discount_rate']) if row['discount_id'] else None,
        })
    return formatted


def _get_discount(discount_id):
    return execute_fetchone('SELECT id, discount_rate FROM discount WHERE id = %s', [discount_id])


@login_required
@csrf_exempt
def apply_platform(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        platform_id = request.POST.get('platform_id')
        if not platform_id:
            return JsonResponse({'success': False, 'message': '平台ID不能为空'})

        platform = _get_platform(platform_id)
        if not platform:
            return JsonResponse({'success': False, 'message': '平台不存在'})

        existing = execute_fetchone(
            'SELECT id, status FROM enter_request WHERE merchant_id = %s AND platform_id = %s',
            [merchant['id'], platform_id],
        )

        if existing:
            status = existing['status']
            if status == 'pending':
                return JsonResponse({'success': False, 'message': '您已经提交过入驻申请，请等待审核'})
            if status == 'approved':
                return JsonResponse({'success': False, 'message': '您已经成功入驻该平台'})
            if status == 'rejected':
                execute_non_query('UPDATE enter_request SET status = %s WHERE id = %s', ['pending', existing['id']])
                return JsonResponse({'success': True, 'message': '入驻申请已重新提交'})

        execute_write(
            'INSERT INTO enter_request (merchant_id, platform_id, status) VALUES (%s, %s, %s)',
            [merchant['id'], platform_id, 'pending'],
        )
        return JsonResponse({'success': True, 'message': '入驻申请提交成功，请等待平台审核'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'申请失败: {str(exc)}'})


@login_required
def add_meal(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        name = request.POST.get('meal-name')
        price = request.POST.get('meal-price')
        meal_type = request.POST.get('meal-type')
        platform_id = request.POST.get('platform-id')

        if not all([name, price, meal_type, platform_id]):
            return JsonResponse({'success': False, 'message': '请填写所有必填字段'})

        platform = _get_platform(platform_id)
        if not platform:
            return JsonResponse({'success': False, 'message': '平台不存在'})

        if not _merchant_joined_platform(merchant['id'], platform_id):
            return JsonResponse({'success': False, 'message': '您尚未入驻该平台，无法添加餐品'})

        try:
            Decimal(price)
        except (InvalidOperation, TypeError):
            return JsonResponse({'success': False, 'message': '价格格式不正确'})

        query = '''
            INSERT INTO meal (merchant_id, platform_id, name, price, meal_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        '''
        meal_id = execute_write(query, [merchant['id'], platform_id, name, price, meal_type])
        return JsonResponse({'success': True, 'message': '餐品添加成功', 'meal_id': meal_id})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'添加失败: {str(exc)}'})


@login_required
def edit_meal(request, meal_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        meal = _get_meal(merchant['id'], meal_id)
        if not meal:
            return JsonResponse({'success': False, 'message': '餐品不存在'})

        name = request.POST.get('meal-name')
        price = request.POST.get('meal-price')
        meal_type = request.POST.get('meal-type')
        platform_id = request.POST.get('platform-id')

        if not all([name, price, meal_type, platform_id]):
            return JsonResponse({'success': False, 'message': '请填写所有必填字段'})

        if not _merchant_joined_platform(merchant['id'], platform_id):
            return JsonResponse({'success': False, 'message': '您尚未入驻该平台，无法修改餐品'})

        try:
            Decimal(price)
        except (InvalidOperation, TypeError):
            return JsonResponse({'success': False, 'message': '价格格式不正确'})

        query = '''
            UPDATE meal
            SET name = %s,
                price = %s,
                meal_type = %s,
                platform_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND merchant_id = %s
        '''
        execute_non_query(query, [name, price, meal_type, platform_id, meal_id, merchant['id']])
        return JsonResponse({'success': True, 'message': '餐品更新成功', 'meal_id': meal_id})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'更新失败: {str(exc)}'})


@login_required
def delete_meal(request, meal_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        meal = _get_meal(merchant['id'], meal_id)
        if not meal:
            return JsonResponse({'success': False, 'message': '餐品不存在'})

        execute_non_query('DELETE FROM meal WHERE id = %s AND merchant_id = %s', [meal_id, merchant['id']])
        return JsonResponse({'success': True, 'message': '餐品删除成功'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'删除失败: {str(exc)}'})


@login_required
def get_meals(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        meals = _get_meals_for_merchant(merchant['id'])
        formatted = []
        for meal in meals:
            formatted.append({
                'id': meal['id'],
                'name': meal['name'],
                'price': str(meal['price']),
                'meal_type': meal['meal_type'],
                'platform_id': meal['platform_id'],
                'platform_name': meal['platform_name'],
                'created_at': meal['created_at'].strftime('%Y-%m-%d %H:%M') if meal['created_at'] else '',
                'meal_type_display': MEAL_TYPE_DISPLAY.get(meal['meal_type'], meal['meal_type']),
            })
        return JsonResponse({'success': True, 'meals': formatted})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'获取餐品失败: {str(exc)}'})


@login_required
def set_discount(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        platform_id = request.POST.get('platform-id')
        discount_id = request.POST.get('discount-id')

        if not all([platform_id, discount_id]):
            return JsonResponse({'success': False, 'message': '请填写所有必填字段'})

        if not _merchant_joined_platform(merchant['id'], platform_id):
            return JsonResponse({'success': False, 'message': '您尚未入驻该平台，无法设置折扣'})

        discount = _get_discount(discount_id)
        if not discount:
            return JsonResponse({'success': False, 'message': '折扣不存在'})

        existing = execute_fetchone(
            'SELECT id FROM merchant_platform_discount WHERE merchant_id = %s AND platform_id = %s',
            [merchant['id'], platform_id],
        )

        if existing:
            execute_non_query(
                'UPDATE merchant_platform_discount SET discount_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s',
                [discount_id, existing['id']],
            )
            discount_id = existing['id']
        else:
            discount_id = execute_write(
                '''
                INSERT INTO merchant_platform_discount
                (merchant_id, platform_id, discount_id, created_at, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''',
                [merchant['id'], platform_id, discount_id],
            )

        return JsonResponse({'success': True, 'message': '折扣设置成功', 'discount_id': discount_id})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'设置失败: {str(exc)}'})


@login_required
def edit_discount(request, discount_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        merchant_discount = execute_fetchone(
            '''
            SELECT id
            FROM merchant_platform_discount
            WHERE id = %s AND merchant_id = %s
            ''',
            [discount_id, merchant['id']],
        )
        if not merchant_discount:
            return JsonResponse({'success': False, 'message': '折扣不存在'})

        new_discount_id = request.POST.get('discount-id')
        if not new_discount_id:
            return JsonResponse({'success': False, 'message': '折扣不能为空'})

        if not _get_discount(new_discount_id):
            return JsonResponse({'success': False, 'message': '折扣不存在'})

        execute_non_query(
            '''
            UPDATE merchant_platform_discount
            SET discount_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            ''',
            [new_discount_id, discount_id],
        )
        return JsonResponse({'success': True, 'message': '折扣更新成功', 'discount_id': discount_id})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'更新失败: {str(exc)}'})


@login_required
def delete_discount(request, discount_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        merchant_discount = execute_fetchone(
            'SELECT id FROM merchant_platform_discount WHERE id = %s AND merchant_id = %s',
            [discount_id, merchant['id']],
        )
        if not merchant_discount:
            return JsonResponse({'success': False, 'message': '折扣不存在'})

        execute_non_query('DELETE FROM merchant_platform_discount WHERE id = %s', [discount_id])
        return JsonResponse({'success': True, 'message': '折扣删除成功'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'删除失败: {str(exc)}'})


@login_required
def get_discounts(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        discounts = _get_discounts_for_merchant(merchant['id'])
        payload = []
        for discount in discounts:
            payload.append({
                'id': discount['id'],
                'platform_id': discount['platform']['id'],
                'platform_name': discount['platform']['platform_name'],
                'discount_id': discount['discount']['id'],
                'discount_rate': str(discount['discount']['discount_rate']),
                'updated_at': discount['updated_at'].strftime('%Y-%m-%d %H:%M') if discount['updated_at'] else '',
            })
        return JsonResponse({'success': True, 'discounts': payload})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'获取折扣数据失败: {str(exc)}'})


@login_required
def get_orders(request):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        order_rows = _get_orders_for_merchant(merchant['id'])
        return JsonResponse({'success': True, 'orders': _format_orders_for_payload(order_rows)})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'获取订单失败: {str(exc)}'})


@login_required
@csrf_exempt
def delete_order(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        merchant = _get_merchant(request.user)
        order_query = f'SELECT id, status FROM {ORDER_TABLE} WHERE id = %s AND merchant_id = %s'
        order = execute_fetchone(order_query, [order_id, merchant['id']])
        if not order:
            return JsonResponse({'success': False, 'message': '订单不存在'})

        if order['status'] != 'unassigned':
            return JsonResponse({'success': False, 'message': '只能删除待分配骑手的订单'})

        execute_non_query(f'DELETE FROM {ORDER_TABLE} WHERE id = %s', [order_id])
        return JsonResponse({'success': True, 'message': '订单删除成功'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '商家信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'删除订单失败: {str(exc)}'})


@login_required
def merchant(request):
    merchant_name = request.session.get('merchant_name', request.user.username)

    try:
        current_merchant = _get_merchant(request.user)
        meals = _format_meals_for_context(_get_meals_for_merchant(current_merchant['id']))
        joined_platforms = _get_platforms_by_status(current_merchant['id'], 'approved')
        applied_platforms = _get_platforms_by_status(current_merchant['id'], 'pending')

        platform_query = f'SELECT id, platform_name, phone FROM {PLATFORM_TABLE} ORDER BY platform_name'
        all_platforms = execute_fetchall(platform_query)
        joined_ids = {platform['id'] for platform in joined_platforms}
        applied_ids = {platform['id'] for platform in applied_platforms}
        not_joined_platforms = [
            platform for platform in all_platforms
            if platform['id'] not in joined_ids and platform['id'] not in applied_ids
        ]

        platform_discounts = _get_discounts_for_merchant(current_merchant['id'])
        available_discounts = _get_available_discounts()
        orders = _format_orders_for_context(_get_orders_for_merchant(current_merchant['id']))
    except ValueError:
        meals = []
        joined_platforms = []
        applied_platforms = []
        not_joined_platforms = []
        platform_discounts = []
        available_discounts = []
        orders = []
        current_merchant = None

    context = {
        'merchant_name': merchant_name,
        'meals': meals,
        'joined_platforms': joined_platforms,
        'applied_platforms': applied_platforms,
        'not_joined_platforms': not_joined_platforms,
        'platform_discounts': platform_discounts,
        'available_discounts': available_discounts,
        'orders': orders,
        'merchant': current_merchant,
    }
    return render(request, 'merchant.html', context)
