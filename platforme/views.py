from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from Project.db_utils import (
    execute_fetchall,
    execute_fetchone,
    execute_non_query,
    get_platform_by_user,
    quote_table,
)


ORDER_STATUS_DISPLAY = {
    'unassigned': '未分配骑手',
    'assigned': '已分配骑手',
    'ready': '顾客待取餐',
    'completed': '已完成',
    'cancelled': '已取消',
}

ORDER_TABLE = quote_table('order')
ORDER_ITEM_TABLE = quote_table('order_item')


def _get_platform(user):
    platform = get_platform_by_user(user.id)
    if not platform:
        raise ValueError('平台信息不存在')
    return platform


def _get_merchant_requests(platform_id, status):
    query = '''
        SELECT er.id,
               m.id AS merchant_id,
               m.merchant_name,
               m.phone,
               m.address
        FROM enter_request er
        JOIN merchant m ON er.merchant_id = m.id
        WHERE er.platform_id = %s AND er.status = %s
        ORDER BY er.id DESC
    '''
    rows = execute_fetchall(query, [platform_id, status])
    return [{
        'id': row['id'],
        'merchant': {
            'id': row['merchant_id'],
            'merchant_name': row['merchant_name'],
            'phone': row['phone'],
            'address': row['address'],
        },
    } for row in rows]


def _get_rider_requests(platform_id, status):
    query = '''
        SELECT sr.id,
               r.id AS rider_id,
               r.rider_name,
               r.phone,
               r.status AS rider_status
        FROM sign_request sr
        JOIN rider r ON sr.rider_id = r.id
        WHERE sr.platform_id = %s AND sr.status = %s
        ORDER BY sr.id DESC
    '''
    rows = execute_fetchall(query, [platform_id, status])
    return [{
        'id': row['id'],
        'rider': {
            'id': row['rider_id'],
            'rider_name': row['rider_name'],
            'phone': row['phone'],
            'status': row['rider_status'],
        },
    } for row in rows]


def _build_in_clause(values):
    return ','.join(['%s'] * len(values))


def _get_orders(platform_id):
    query = f'''
        SELECT o.id,
               o.price,
               o.status,
               o.created_at,
               c.customer_name,
               m.merchant_name,
               r.rider_name
        FROM {ORDER_TABLE} o
        JOIN customer c ON o.customer_id = c.id
        JOIN merchant m ON o.merchant_id = m.id
        LEFT JOIN rider r ON o.rider_id = r.id
        WHERE o.platform_id = %s
        ORDER BY o.created_at DESC
    '''
    orders = execute_fetchall(query, [platform_id])
    if not orders:
        return []

    order_map = {order['id']: order for order in orders}
    for order in order_map.values():
        order['meals'] = []

    order_ids = list(order_map.keys())
    placeholders = _build_in_clause(order_ids)
    items_query = f'''
        SELECT oi.order_id,
               oi.id,
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
            'item_id': item['id'],
            'name': item['meal_name'],
            'quantity': item['quantity'],
            'unit_price': item['unit_price'],
            'line_price': item['line_price'],
        })

    return orders


def _format_meal_summary(meals):
    if not meals:
        return ''
    return ', '.join(f"{meal['name']} x{meal['quantity']}" for meal in meals)


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
            'merchant': {'merchant_name': row['merchant_name']},
            'meals': row.get('meals', []),
            'meal_summary': _format_meal_summary(row.get('meals', [])),
            'rider': {'rider_name': row['rider_name']} if row['rider_name'] else None,
        })
    return formatted


def _get_order_counts(order_rows):
    total = len(order_rows)
    unassigned = sum(1 for row in order_rows if row['status'] == 'unassigned')
    assigned = sum(1 for row in order_rows if row['status'] == 'assigned')
    ready = sum(1 for row in order_rows if row['status'] == 'ready')
    return total, unassigned, assigned, ready


def _get_enter_request_entry(platform_id, request_id, status):
    query = '''
        SELECT id
        FROM enter_request
        WHERE id = %s AND platform_id = %s AND status = %s
    '''
    return execute_fetchone(query, [request_id, platform_id, status])


def _get_sign_request_entry(platform_id, request_id, status):
    query = '''
        SELECT sr.id, sr.rider_id
        FROM sign_request sr
        WHERE sr.id = %s AND sr.platform_id = %s AND sr.status = %s
    '''
    return execute_fetchone(query, [request_id, platform_id, status])


@login_required
def platform(request):
    try:
        current_platform = _get_platform(request.user)
        platform_name = current_platform['platform_name']

        pending_merchants = _get_merchant_requests(current_platform['id'], 'pending')
        approved_merchants = _get_merchant_requests(current_platform['id'], 'approved')
        pending_riders = _get_rider_requests(current_platform['id'], 'pending')
        approved_riders = _get_rider_requests(current_platform['id'], 'approved')
        order_rows = _get_orders(current_platform['id'])
        orders = _format_orders_for_context(order_rows)
        total_orders, unassigned_orders, assigned_orders, ready_orders = _get_order_counts(order_rows)

        context = {
            'platform_name': platform_name,
            'pending_merchant_requests': pending_merchants,
            'approved_merchant_requests': approved_merchants,
            'pending_rider_requests': pending_riders,
            'approved_rider_requests': approved_riders,
            'orders': orders,
            'total_orders': total_orders,
            'unassigned_orders': unassigned_orders,
            'assigned_orders': assigned_orders,
            'ready_orders': ready_orders,
        }
    except ValueError:
        platform_name = request.session.get('platform_name', request.user.username)
        context = {
            'platform_name': platform_name,
            'pending_merchant_requests': [],
            'approved_merchant_requests': [],
            'pending_rider_requests': [],
            'approved_rider_requests': [],
            'orders': [],
            'total_orders': 0,
            'unassigned_orders': 0,
            'assigned_orders': 0,
            'ready_orders': 0,
        }

    return render(request, 'platform.html', context)


@login_required
@csrf_exempt
def approve_merchant_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        enter_request = _get_enter_request_entry(platform['id'], request_id, 'pending')
        if not enter_request:
            return JsonResponse({'success': False, 'message': '申请不存在或状态已更新'})

        execute_non_query('UPDATE enter_request SET status = %s WHERE id = %s', ['approved', request_id])
        return JsonResponse({'success': True, 'message': '商家入驻申请已通过'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def reject_merchant_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        enter_request = _get_enter_request_entry(platform['id'], request_id, 'pending')
        if not enter_request:
            return JsonResponse({'success': False, 'message': '申请不存在或状态已更新'})

        execute_non_query('DELETE FROM enter_request WHERE id = %s', [request_id])
        return JsonResponse({'success': True, 'message': '商家入驻申请已拒绝'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def remove_merchant(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        enter_request = _get_enter_request_entry(platform['id'], request_id, 'approved')
        if not enter_request:
            return JsonResponse({'success': False, 'message': '商家未入驻或申请不存在'})

        execute_non_query('DELETE FROM enter_request WHERE id = %s', [request_id])
        return JsonResponse({'success': True, 'message': '商家已移除'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def approve_rider_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        sign_request = _get_sign_request_entry(platform['id'], request_id, 'pending')
        if not sign_request:
            return JsonResponse({'success': False, 'message': '申请不存在或状态已更新'})

        execute_non_query('UPDATE sign_request SET status = %s WHERE id = %s', ['approved', request_id])
        execute_non_query('UPDATE rider SET status = %s WHERE id = %s', ['online', sign_request['rider_id']])
        return JsonResponse({'success': True, 'message': '骑手签约申请已通过'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def reject_rider_request(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        sign_request = _get_sign_request_entry(platform['id'], request_id, 'pending')
        if not sign_request:
            return JsonResponse({'success': False, 'message': '申请不存在或状态已更新'})

        execute_non_query('DELETE FROM sign_request WHERE id = %s', [request_id])
        return JsonResponse({'success': True, 'message': '骑手签约申请已拒绝'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def remove_rider(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        request_id = request.POST.get('request_id')
        if not request_id:
            return JsonResponse({'success': False, 'message': '申请ID不能为空'})

        sign_request = _get_sign_request_entry(platform['id'], request_id, 'approved')
        if not sign_request:
            return JsonResponse({'success': False, 'message': '骑手未签约或申请不存在'})

        execute_non_query('UPDATE rider SET status = %s WHERE id = %s', ['offline', sign_request['rider_id']])
        execute_non_query('DELETE FROM sign_request WHERE id = %s', [request_id])
        return JsonResponse({'success': True, 'message': '骑手已移除'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})


@login_required
@csrf_exempt
def delete_order(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})

    try:
        platform = _get_platform(request.user)
        order_id = request.POST.get('order_id')
        if not order_id:
            return JsonResponse({'success': False, 'message': '订单ID不能为空'})

        order_query = f'''
            SELECT id, status
            FROM {ORDER_TABLE}
            WHERE id = %s AND platform_id = %s
        '''
        order = execute_fetchone(order_query, [order_id, platform['id']])
        if not order:
            return JsonResponse({'success': False, 'message': '订单不存在'})

        if order['status'] != 'unassigned':
            return JsonResponse({'success': False, 'message': '只能删除待分配骑手的订单'})

        execute_non_query(f'DELETE FROM {ORDER_TABLE} WHERE id = %s', [order_id])
        return JsonResponse({'success': True, 'message': '订单删除成功'})
    except ValueError:
        return JsonResponse({'success': False, 'message': '平台信息不存在'})
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'操作失败: {str(exc)}'})
