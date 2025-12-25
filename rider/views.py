from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from Project.db_utils import (
    execute_fetchall,
    execute_fetchone,
    execute_non_query,
    execute_write,
    get_rider_by_user,
    quote_table,
)


def _get_rider(user):
    rider = get_rider_by_user(user.id)
    if not rider:
        raise ValueError('骑手信息不存在')
    return rider


PLATFORM_TABLE = quote_table('platform')
ORDER_TABLE = quote_table('order')
ORDER_ITEM_TABLE = quote_table('order_item')
ORDER_STATUS_DISPLAY = {
    'unassigned': '未分配骑手',
    'assigned': '已分配骑手',
    'ready': '顾客待取餐',
    'completed': '已完成',
    'cancelled': '已取消',
}


def _get_platform(platform_id):
    query = f'SELECT id, platform_name FROM {PLATFORM_TABLE} WHERE id = %s'
    return execute_fetchone(query, [platform_id])


def _has_sign_request(rider_id):
    query = 'SELECT 1 FROM sign_request WHERE rider_id = %s LIMIT 1'
    return execute_fetchone(query, [rider_id]) is not None


def _get_platforms_by_status(rider_id, status):
    query = f'''
        SELECT p.id, p.platform_name, p.phone
        FROM sign_request sr
        JOIN {PLATFORM_TABLE} p ON sr.platform_id = p.id
        WHERE sr.rider_id = %s AND sr.status = %s
        ORDER BY p.platform_name
    '''
    return execute_fetchall(query, [rider_id, status])


def _get_signed_platform_ids(rider_id):
    query = 'SELECT platform_id FROM sign_request WHERE rider_id = %s AND status = %s'
    rows = execute_fetchall(query, [rider_id, 'approved'])
    return [row['platform_id'] for row in rows]


def _build_in_clause(values):
    return ','.join(['%s'] * len(values))


def _format_meal_summary(meals):
    if not meals:
        return ''
    return ', '.join(f"{meal['name']} x{meal['quantity']}" for meal in meals)


def _attach_meal_summaries(order_rows):
    if not order_rows:
        return []
    order_map = {order['id']: order for order in order_rows}
    for order in order_map.values():
        order['meals'] = []

    order_ids = list(order_map.keys())
    placeholders = _build_in_clause(order_ids)
    items_query = f'''
        SELECT oi.order_id,
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
    for item in items:
        order_map[item['order_id']]['meals'].append({
            'name': item['meal_name'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'line_price': item['line_price'],
        })
    for order in order_map.values():
        order['meal_summary'] = _format_meal_summary(order['meals'])
        order['status_display'] = ORDER_STATUS_DISPLAY.get(order.get('status'), order.get('status'))
    return list(order_map.values())


def _get_unassigned_order_groups(platform_ids):
    if not platform_ids:
        return []

    placeholders = _build_in_clause(platform_ids)
    query = f'''
        SELECT o.id,
               o.price,
               o.status,
               o.created_at,
               o.merchant_id,
               m.merchant_name,
               o.customer_id,
               c.customer_name
        FROM {ORDER_TABLE} o
        JOIN merchant m ON o.merchant_id = m.id
        JOIN customer c ON o.customer_id = c.id
        WHERE o.platform_id IN ({placeholders})
          AND o.rider_id IS NULL
          AND o.status = 'unassigned'
        ORDER BY o.created_at DESC
    '''
    orders = execute_fetchall(query, platform_ids)
    return _attach_meal_summaries(orders)


def _get_accepted_order_groups(rider_id):
    query = f'''
        SELECT o.id,
               o.price,
               o.status,
               o.created_at,
               o.merchant_id,
               m.merchant_name,
               o.customer_id,
               c.customer_name
        FROM {ORDER_TABLE} o
        JOIN merchant m ON o.merchant_id = m.id
        JOIN customer c ON o.customer_id = c.id
        WHERE o.rider_id = %s
          AND o.status IN ('assigned', 'ready')
        ORDER BY o.created_at DESC
    '''
    orders = execute_fetchall(query, [rider_id])
    return _attach_meal_summaries(orders)


@login_required
@csrf_exempt
def apply_platform(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        rider = _get_rider(request.user)
        if _has_sign_request(rider['id']):
            return JsonResponse({'success': False, 'message': '您已经申请或签约了平台，不能再次申请'})

        platform_id = request.POST.get('platform_id')
        if not platform_id:
            return JsonResponse({'success': False, 'message': '平台ID不能为空'})

        platform = _get_platform(platform_id)
        if not platform:
            return JsonResponse({'success': False, 'message': '平台不存在'})

        execute_write(
            'INSERT INTO sign_request (rider_id, platform_id, status) VALUES (%s, %s, %s)',
            [rider['id'], platform_id, 'pending'],
        )
        return JsonResponse({'success': True, 'message': '签约申请提交成功，请等待平台审核'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '骑手信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'申请失败: {str(exc)}'})


@login_required
@csrf_exempt
def accept_orders(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        rider = _get_rider(request.user)
        signed_platform_ids = _get_signed_platform_ids(rider['id'])
        if not signed_platform_ids:
            return JsonResponse({'success': False, 'message': '您尚未签约任何平台，无法接单'})

        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'success': False, 'message': '订单ID不能为空'})

        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': '订单ID无效'})

        placeholders = _build_in_clause(signed_platform_ids)
        query = f'''
            SELECT id
            FROM {ORDER_TABLE}
            WHERE id = %s
              AND platform_id IN ({placeholders})
              AND rider_id IS NULL
              AND status = 'unassigned'
        '''
        params = [order_id_int, *signed_platform_ids]
        order = execute_fetchone(query, params)
        if not order:
            return JsonResponse({'success': False, 'message': '没有找到对应的订单'})

        execute_non_query(
            f'''
            UPDATE {ORDER_TABLE}
            SET rider_id = %s,
                status = 'assigned'
            WHERE id = %s
            ''',
            [rider['id'], order_id_int],
        )
        return JsonResponse({'success': True, 'message': '成功接取订单'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '骑手信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'接单失败: {str(exc)}'})


@login_required
@csrf_exempt
def cancel_orders(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        rider = _get_rider(request.user)
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'success': False, 'message': '订单ID不能为空'})

        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': '订单ID无效'})

        order = execute_fetchone(
            f'''
            SELECT id
            FROM {ORDER_TABLE}
            WHERE rider_id = %s
              AND status IN ('assigned', 'ready')
              AND id = %s
            ''',
            [rider['id'], order_id_int],
        )
        if not order:
            return JsonResponse({'success': False, 'message': '没有找到对应的订单'})

        execute_non_query(
            f'''
            UPDATE {ORDER_TABLE}
            SET rider_id = NULL,
                status = 'unassigned'
            WHERE id = %s
            ''',
            [order_id_int],
        )
        return JsonResponse({'success': True, 'message': '成功取消订单'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '骑手信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'取消订单失败: {str(exc)}'})


@login_required
@csrf_exempt
def complete_orders(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        rider = _get_rider(request.user)
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'success': False, 'message': '订单ID不能为空'})

        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': '订单ID无效'})

        order = execute_fetchone(
            f'''
            SELECT id
            FROM {ORDER_TABLE}
            WHERE rider_id = %s
              AND status IN ('assigned', 'ready')
              AND id = %s
            ''',
            [rider['id'], order_id_int],
        )
        if not order:
            return JsonResponse({'success': False, 'message': '没有找到对应的订单'})

        execute_non_query(
            f'''
            UPDATE {ORDER_TABLE}
            SET status = 'ready'
            WHERE id = %s
            ''',
            [order_id_int],
        )
        return JsonResponse({'success': True, 'message': '订单状态已更新为待取餐'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '骑手信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'完成订单失败: {str(exc)}'})


@login_required
def rider(request):
    rider_name = request.session.get('rider_name', request.user.username)

    try:
        current_rider = _get_rider(request.user)
        platform_query = f'SELECT id, platform_name, phone FROM {PLATFORM_TABLE} ORDER BY platform_name'
        all_platforms = execute_fetchall(platform_query)
        signed_platforms = _get_platforms_by_status(current_rider['id'], 'approved')
        applied_platforms = _get_platforms_by_status(current_rider['id'], 'pending')

        signed_ids = {platform['id'] for platform in signed_platforms}
        applied_ids = {platform['id'] for platform in applied_platforms}
        not_signed_platforms = [
            platform for platform in all_platforms
            if platform['id'] not in signed_ids and platform['id'] not in applied_ids
        ]

        signed_platform_ids = [platform['id'] for platform in signed_platforms]
        unassigned_orders = _get_unassigned_order_groups(signed_platform_ids)
        accepted_orders = _get_accepted_order_groups(current_rider['id'])
    except ValueError:
        current_rider = None
        signed_platforms = []
        applied_platforms = []
        not_signed_platforms = []
        unassigned_orders = []
        accepted_orders = []

    context = {
        'rider_name': rider_name,
        'unassigned_orders': unassigned_orders,
        'accepted_orders': accepted_orders,
        'signed_platforms': signed_platforms,
        'applied_platforms': applied_platforms,
        'not_signed_platforms': not_signed_platforms,
        'rider': current_rider,
    }
    return render(request, 'rider.html', context)
