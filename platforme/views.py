from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from login.models import Platform, Merchant, Rider, EnterRequest, SignRequest
from order.models import Order


@login_required
def platform(request):
    try:
        # 获取当前平台对象
        current_platform = Platform.objects.get(user_profile__user=request.user)
        platform_name = current_platform.platform_name

        # 获取待审核的商家入驻申请（审核中状态）
        pending_merchant_requests = EnterRequest.objects.filter(
            platform=current_platform,
            status='pending'
        ).select_related('merchant')

        # 获取已通过的商家入驻申请（已入驻商家）
        approved_merchant_requests = EnterRequest.objects.filter(
            platform=current_platform,
            status='approved'
        ).select_related('merchant')

        # 获取待审核的骑手签约申请（审核中状态）
        pending_rider_requests = SignRequest.objects.filter(
            platform=current_platform,
            status='pending'
        ).select_related('rider')

        # 获取已通过的骑手签约申请（已签约骑手）
        approved_rider_requests = SignRequest.objects.filter(
            platform=current_platform,
            status='approved'
        ).select_related('rider')

        # 获取平台所有订单
        orders = Order.objects.filter(
            platform=current_platform
        ).select_related(
            'customer', 'merchant', 'meal', 'rider', 'discount'
        ).order_by('-created_at')

        # 订单统计 - 只统计三种状态
        total_orders = orders.count()
        unassigned_orders = orders.filter(status='unassigned').count()
        assigned_orders = orders.filter(status='assigned').count()
        ready_orders = orders.filter(status='ready').count()

        context = {
            'platform_name': platform_name,
            'pending_merchant_requests': pending_merchant_requests,
            'approved_merchant_requests': approved_merchant_requests,
            'pending_rider_requests': pending_rider_requests,
            'approved_rider_requests': approved_rider_requests,
            'orders': orders,
            'total_orders': total_orders,
            'unassigned_orders': unassigned_orders,
            'assigned_orders': assigned_orders,
            'ready_orders': ready_orders,
        }
    except Platform.DoesNotExist:
        # 如果平台信息不存在，使用空列表
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
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取入驻申请对象
            enter_request = get_object_or_404(
                EnterRequest,
                id=request_id,
                platform=current_platform,
                status='pending'  # 只处理待审核的申请
            )

            # 更新申请状态为已通过
            enter_request.status = 'approved'
            enter_request.save()

            return JsonResponse({
                'success': True,
                'message': '商家入驻申请已通过'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def reject_merchant_request(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取入驻申请对象
            enter_request = get_object_or_404(
                EnterRequest,
                id=request_id,
                platform=current_platform,
                status='pending'  # 只处理待审核的申请
            )

            # 删除申请记录
            enter_request.delete()

            return JsonResponse({
                'success': True,
                'message': '商家入驻申请已拒绝'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def remove_merchant(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取入驻申请对象（已通过的申请）
            enter_request = get_object_or_404(
                EnterRequest,
                id=request_id,
                platform=current_platform,
                status='approved'
            )

            # 删除申请记录
            enter_request.delete()

            return JsonResponse({
                'success': True,
                'message': '商家已移除'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def approve_rider_request(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取签约申请对象
            sign_request = get_object_or_404(
                SignRequest,
                id=request_id,
                platform=current_platform,
                status='pending'  # 只处理待审核的申请
            )

            # 更新申请状态为已通过
            sign_request.status = 'approved'
            sign_request.save()

            # 更新骑手状态为在线
            rider = sign_request.rider
            rider.status = 'online'
            rider.save()

            return JsonResponse({
                'success': True,
                'message': '骑手签约申请已通过'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def reject_rider_request(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取签约申请对象
            sign_request = get_object_or_404(
                SignRequest,
                id=request_id,
                platform=current_platform,
                status='pending'  # 只处理待审核的申请
            )

            # 删除申请记录
            sign_request.delete()

            return JsonResponse({
                'success': True,
                'message': '骑手签约申请已拒绝'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def remove_rider(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取申请ID
            request_id = request.POST.get('request_id')

            if not request_id:
                return JsonResponse({
                    'success': False,
                    'message': '申请ID不能为空'
                })

            # 获取签约申请对象（已通过的申请）
            sign_request = get_object_or_404(
                SignRequest,
                id=request_id,
                platform=current_platform,
                status='approved'
            )

            # 更新骑手状态为离线
            rider = sign_request.rider
            rider.status = 'offline'
            rider.save()

            # 删除申请记录
            sign_request.delete()

            return JsonResponse({
                'success': True,
                'message': '骑手已移除'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def delete_order(request):
    if request.method == 'POST':
        try:
            # 获取当前平台
            current_platform = Platform.objects.get(user_profile__user=request.user)

            # 获取订单ID
            order_id = request.POST.get('order_id')

            if not order_id:
                return JsonResponse({
                    'success': False,
                    'message': '订单ID不能为空'
                })

            # 获取订单对象（只允许删除待分配骑手的订单）
            order = get_object_or_404(
                Order,
                id=order_id,
                platform=current_platform,
                status='unassigned'  # 只允许删除待分配骑手的订单
            )

            # 删除订单
            order.delete()

            return JsonResponse({
                'success': True,
                'message': '订单删除成功'
            })

        except Platform.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '平台信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'操作失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})