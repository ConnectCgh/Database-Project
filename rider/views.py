from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum

from login.models import Platform, Rider, SignRequest
from order.models import Order


@login_required
@csrf_exempt
def apply_platform(request):
    if request.method == 'POST':
        try:
            # 获取当前骑手
            current_rider = Rider.objects.get(user_profile__user=request.user)

            # 检查是否已经签约或申请过任何平台
            existing_requests = SignRequest.objects.filter(rider=current_rider)
            if existing_requests.exists():
                return JsonResponse({
                    'success': False,
                    'message': '您已经申请或签约了平台，不能再次申请'
                })

            # 获取平台ID
            platform_id = request.POST.get('platform_id')

            if not platform_id:
                return JsonResponse({
                    'success': False,
                    'message': '平台ID不能为空'
                })

            # 获取平台对象
            platform = get_object_or_404(Platform, id=platform_id)

            # 创建新的签约申请
            sign_request = SignRequest.objects.create(
                rider=current_rider,
                platform=platform,
                status='pending'
            )

            return JsonResponse({
                'success': True,
                'message': '签约申请提交成功，请等待平台审核'
            })

        except Rider.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '骑手信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'申请失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def accept_orders(request):
    if request.method == 'POST':
        try:
            # 获取当前骑手
            current_rider = Rider.objects.get(user_profile__user=request.user)

            # 检查骑手是否已签约平台
            signed_platforms = Platform.objects.filter(
                signrequest__rider=current_rider,
                signrequest__status='approved'
            ).distinct()

            if not signed_platforms.exists():
                return JsonResponse({
                    'success': False,
                    'message': '您尚未签约任何平台，无法接单'
                })

            # 获取商家ID和顾客ID
            merchant_id = request.POST.get('merchant_id')
            customer_id = request.POST.get('customer_id')

            if not merchant_id or not customer_id:
                return JsonResponse({
                    'success': False,
                    'message': '商家ID和顾客ID不能为空'
                })

            # 获取该商家和顾客的所有未分配订单
            orders = Order.objects.filter(
                platform__in=signed_platforms,
                rider=None,
                status='unassigned',
                merchant_id=merchant_id,
                customer_id=customer_id
            )

            if not orders.exists():
                return JsonResponse({
                    'success': False,
                    'message': '没有找到对应的订单'
                })

            # 批量更新订单
            orders.update(
                rider=current_rider,
                status='assigned'
            )

            return JsonResponse({
                'success': True,
                'message': f'成功接取订单'
            })

        except Rider.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '骑手信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'接单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def cancel_orders(request):
    if request.method == 'POST':
        try:
            # 获取当前骑手
            current_rider = Rider.objects.get(user_profile__user=request.user)

            # 获取商家ID和顾客ID
            merchant_id = request.POST.get('merchant_id')
            customer_id = request.POST.get('customer_id')

            if not merchant_id or not customer_id:
                return JsonResponse({
                    'success': False,
                    'message': '商家ID和顾客ID不能为空'
                })

            # 获取该商家和顾客的所有已分配订单
            orders = Order.objects.filter(
                rider=current_rider,
                status__in=['assigned', 'ready'],
                merchant_id=merchant_id,
                customer_id=customer_id
            )

            if not orders.exists():
                return JsonResponse({
                    'success': False,
                    'message': '没有找到对应的订单'
                })

            # 批量取消订单
            orders.update(
                rider=None,
                status='unassigned'
            )

            return JsonResponse({
                'success': True,
                'message': f'成功取消订单'
            })

        except Rider.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '骑手信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'取消订单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def complete_orders(request):
    if request.method == 'POST':
        try:
            # 获取当前骑手
            current_rider = Rider.objects.get(user_profile__user=request.user)

            # 获取商家ID和顾客ID
            merchant_id = request.POST.get('merchant_id')
            customer_id = request.POST.get('customer_id')

            if not merchant_id or not customer_id:
                return JsonResponse({
                    'success': False,
                    'message': '商家ID和顾客ID不能为空'
                })

            # 获取该商家和顾客的所有已分配订单
            orders = Order.objects.filter(
                rider=current_rider,
                status__in=['assigned', 'ready'],
                merchant_id=merchant_id,
                customer_id=customer_id
            )

            if not orders.exists():
                return JsonResponse({
                    'success': False,
                    'message': '没有找到对应的订单'
                })

            # 批量完成订单
            orders.update(status='ready')

            return JsonResponse({
                'success': True,
                'message': f'成功完成{orders.count()}个订单'
            })

        except Rider.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '骑手信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'完成订单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


def rider(request):
    # 直接从session获取用户名作为骑手名
    rider_name = request.session.get('rider_name', request.user.username)

    try:
        # 获取当前骑手对象
        current_rider = Rider.objects.get(user_profile__user=request.user)

        # 获取所有平台
        all_platforms = Platform.objects.all()

        # 获取当前骑手已签约的平台（状态为approved）
        signed_platforms = Platform.objects.filter(
            signrequest__rider=current_rider,
            signrequest__status='approved'
        ).distinct()

        # 获取当前骑手已申请但未签约的平台（状态为pending）
        applied_platforms = Platform.objects.filter(
            signrequest__rider=current_rider,
            signrequest__status='pending'
        ).distinct()

        # 获取未申请的平台（排除已申请和已签约的）
        signed_platform_ids = signed_platforms.values_list('id', flat=True)
        applied_platform_ids = applied_platforms.values_list('id', flat=True)
        not_signed_platforms = all_platforms.exclude(
            id__in=signed_platform_ids
        ).exclude(
            id__in=applied_platform_ids
        )

        # 获取待接订单分组（按商家和顾客分组）
        unassigned_order_groups = Order.objects.filter(
            platform__in=signed_platforms,
            rider=None,
            status='unassigned'
        ).values(
            'merchant_id', 'merchant__merchant_name',
            'customer_id', 'customer__customer_name'
        ).annotate(
            total_price=Sum('price')
        ).order_by('merchant__merchant_name', 'customer__customer_name')

        # 获取已接收订单分组（按商家和顾客分组）
        accepted_order_groups = Order.objects.filter(
            rider=current_rider,
            status__in=['assigned']
        ).values(
            'merchant_id', 'merchant__merchant_name',
            'customer_id', 'customer__customer_name'
        ).annotate(
            total_price=Sum('price')
        ).order_by('merchant__merchant_name', 'customer__customer_name')

    except Rider.DoesNotExist:
        # 如果骑手信息不存在，使用空列表
        unassigned_order_groups = []
        accepted_order_groups = []
        signed_platforms = []
        applied_platforms = []
        not_signed_platforms = []
        current_rider = None

    context = {
        'rider_name': rider_name,
        'unassigned_order_groups': unassigned_order_groups,
        'accepted_order_groups': accepted_order_groups,
        'signed_platforms': signed_platforms,
        'applied_platforms': applied_platforms,
        'not_signed_platforms': not_signed_platforms,
        'rider': current_rider,
    }

    return render(request, 'rider.html', context)