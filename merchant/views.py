from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from meal.models import Meal
from login.models import Platform, Merchant, EnterRequest, MerchantPlatformDiscount
from discount.models import Discount
from order.models import Order


@login_required
@csrf_exempt
def apply_platform(request):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取平台ID
            platform_id = request.POST.get('platform_id')

            if not platform_id:
                return JsonResponse({
                    'success': False,
                    'message': '平台ID不能为空'
                })

            # 获取平台对象
            platform = get_object_or_404(Platform, id=platform_id)

            # 检查是否已经申请过
            existing_request = EnterRequest.objects.filter(
                merchant=current_merchant,
                platform=platform
            ).first()

            if existing_request:
                if existing_request.status == 'pending':
                    return JsonResponse({
                        'success': False,
                        'message': '您已经提交过入驻申请，请等待审核'
                    })
                elif existing_request.status == 'approved':
                    return JsonResponse({
                        'success': False,
                        'message': '您已经成功入驻该平台'
                    })
                elif existing_request.status == 'rejected':
                    # 如果是被拒绝的申请，可以重新提交
                    existing_request.status = 'pending'
                    existing_request.save()

                    return JsonResponse({
                        'success': True,
                        'message': '入驻申请已重新提交'
                    })

            # 创建新的入驻申请
            enter_request = EnterRequest.objects.create(
                merchant=current_merchant,
                platform=platform,
                status='pending'
            )

            return JsonResponse({
                'success': True,
                'message': '入驻申请提交成功，请等待平台审核'
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'申请失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def add_meal(request):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取表单数据
            name = request.POST.get('meal-name')
            price = request.POST.get('meal-price')
            meal_type = request.POST.get('meal-type')
            platform_id = request.POST.get('platform-id')

            # 数据验证
            if not all([name, price, meal_type, platform_id]):
                return JsonResponse({
                    'success': False,
                    'message': '请填写所有必填字段'
                })

            # 获取平台对象
            platform = get_object_or_404(Platform, id=platform_id)

            # 检查商家是否已入驻该平台
            if not EnterRequest.objects.filter(
                    merchant=current_merchant,
                    platform=platform,
                    status='approved'
            ).exists():
                return JsonResponse({
                    'success': False,
                    'message': '您尚未入驻该平台，无法添加餐品'
                })

            # 创建餐品记录
            meal = Meal.objects.create(
                merchant=current_merchant,
                platform=platform,
                name=name,
                price=price,
                meal_type=meal_type
            )

            return JsonResponse({
                'success': True,
                'message': '餐品添加成功',
                'meal_id': meal.id
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'添加失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def edit_meal(request, meal_id):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取餐品对象，确保属于当前商家
            meal = get_object_or_404(Meal, id=meal_id, merchant=current_merchant)

            # 获取表单数据
            name = request.POST.get('meal-name')
            price = request.POST.get('meal-price')
            meal_type = request.POST.get('meal-type')
            platform_id = request.POST.get('platform-id')

            # 数据验证
            if not all([name, price, meal_type, platform_id]):
                return JsonResponse({
                    'success': False,
                    'message': '请填写所有必填字段'
                })

            # 获取平台对象
            platform = get_object_or_404(Platform, id=platform_id)

            # 检查商家是否已入驻该平台
            if not EnterRequest.objects.filter(
                    merchant=current_merchant,
                    platform=platform,
                    status='approved'
            ).exists():
                return JsonResponse({
                    'success': False,
                    'message': '您尚未入驻该平台，无法修改餐品'
                })

            # 更新餐品记录
            meal.name = name
            meal.price = price
            meal.meal_type = meal_type
            meal.platform = platform
            meal.save()

            return JsonResponse({
                'success': True,
                'message': '餐品更新成功',
                'meal_id': meal.id
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'更新失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def delete_meal(request, meal_id):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取餐品对象，确保属于当前商家
            meal = get_object_or_404(Meal, id=meal_id, merchant=current_merchant)

            # 删除餐品
            meal.delete()

            return JsonResponse({
                'success': True,
                'message': '餐品删除成功'
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'删除失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def get_meals(request):
    if request.method == 'GET':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取当前商家的所有餐品
            meals = Meal.objects.filter(merchant=current_merchant).order_by('-created_at')

            # 序列化餐品数据
            meals_data = []
            for meal in meals:
                meals_data.append({
                    'id': meal.id,
                    'name': meal.name,
                    'price': str(meal.price),  # 转换为字符串避免序列化问题
                    'meal_type': meal.meal_type,
                    'platform_id': meal.platform.id,
                    'platform_name': meal.platform.platform_name,
                    'created_at': meal.created_at.strftime('%Y-%m-%d %H:%M')
                })

            return JsonResponse({
                'success': True,
                'meals': meals_data
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'获取餐品失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def set_discount(request):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取表单数据
            platform_id = request.POST.get('platform-id')
            discount_id = request.POST.get('discount-id')

            # 数据验证
            if not all([platform_id, discount_id]):
                return JsonResponse({
                    'success': False,
                    'message': '请填写所有必填字段'
                })

            # 获取平台对象
            platform = get_object_or_404(Platform, id=platform_id)

            # 检查商家是否已入驻该平台
            if not EnterRequest.objects.filter(
                    merchant=current_merchant,
                    platform=platform,
                    status='approved'
            ).exists():
                return JsonResponse({
                    'success': False,
                    'message': '您尚未入驻该平台，无法设置折扣'
                })

            # 获取折扣对象
            discount = get_object_or_404(Discount, id=discount_id)

            # 创建或更新商家平台折扣关系
            merchant_discount, created = MerchantPlatformDiscount.objects.update_or_create(
                merchant=current_merchant,
                platform=platform,
                defaults={'discount': discount}
            )

            return JsonResponse({
                'success': True,
                'message': '折扣设置成功',
                'discount_id': merchant_discount.id
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'设置失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def edit_discount(request, discount_id):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取折扣关系对象，确保属于当前商家
            merchant_discount = get_object_or_404(
                MerchantPlatformDiscount,
                id=discount_id,
                merchant=current_merchant
            )

            # 获取表单数据
            new_discount_id = request.POST.get('discount-id')

            # 数据验证
            if not new_discount_id:
                return JsonResponse({
                    'success': False,
                    'message': '折扣不能为空'
                })

            # 获取新的折扣对象
            new_discount = get_object_or_404(Discount, id=new_discount_id)

            # 更新折扣关系
            merchant_discount.discount = new_discount
            merchant_discount.save()

            return JsonResponse({
                'success': True,
                'message': '折扣更新成功',
                'discount_id': merchant_discount.id
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'更新失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def delete_discount(request, discount_id):
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取折扣关系对象，确保属于当前商家
            merchant_discount = get_object_or_404(
                MerchantPlatformDiscount,
                id=discount_id,
                merchant=current_merchant
            )

            # 删除折扣关系
            merchant_discount.delete()

            return JsonResponse({
                'success': True,
                'message': '折扣删除成功'
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'删除失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def get_discounts(request):
    if request.method == 'GET':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取当前商家的所有折扣设置
            discounts = MerchantPlatformDiscount.objects.filter(
                merchant=current_merchant
            ).select_related('platform', 'discount').order_by('-updated_at')

            # 序列化折扣数据
            discounts_data = []
            for discount in discounts:
                discounts_data.append({
                    'id': discount.id,
                    'platform_id': discount.platform.id,
                    'platform_name': discount.platform.platform_name,
                    'discount_id': discount.discount.id,
                    'discount_rate': str(discount.discount.discount_rate),
                    'updated_at': discount.updated_at.strftime('%Y-%m-%d %H:%M')
                })

            return JsonResponse({
                'success': True,
                'discounts': discounts_data
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'获取折扣数据失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


# 订单管理相关视图
@login_required
def get_orders(request):
    """获取当前商家的所有订单"""
    if request.method == 'GET':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取当前商家的所有订单
            orders = Order.objects.filter(merchant=current_merchant).select_related(
                'customer', 'platform', 'meal', 'rider', 'discount'
            ).order_by('-created_at')

            # 序列化订单数据
            orders_data = []
            for order in orders:
                orders_data.append({
                    'id': order.id,
                    'customer_name': order.customer.customer_name,
                    'platform_name': order.platform.platform_name,
                    'meal_name': order.meal.name,
                    'price': str(order.price),
                    'rider_name': order.rider.rider_name if order.rider else None,
                    'status': order.status,
                    'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
                    'discount_rate': str(order.discount.discount_rate) if order.discount else None
                })

            return JsonResponse({
                'success': True,
                'orders': orders_data
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'获取订单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def delete_order(request, order_id):
    """删除待分配骑手的订单"""
    if request.method == 'POST':
        try:
            # 获取当前商家
            current_merchant = Merchant.objects.get(user_profile__user=request.user)

            # 获取订单对象，确保属于当前商家
            order = get_object_or_404(Order, id=order_id, merchant=current_merchant)

            # 检查订单状态，只有待分配骑手的订单可以删除
            if order.status != 'unassigned':
                return JsonResponse({
                    'success': False,
                    'message': '只能删除待分配骑手的订单'
                })

            # 删除订单
            order.delete()

            return JsonResponse({
                'success': True,
                'message': '订单删除成功'
            })

        except Merchant.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家信息不存在'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'删除订单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def merchant(request):
    # 直接从session获取用户名作为商家名
    merchant_name = request.session.get('merchant_name', request.user.username)

    try:
        # 获取当前商家对象
        current_merchant = Merchant.objects.get(user_profile__user=request.user)

        # 获取当前商家的所有餐品
        meals = Meal.objects.filter(merchant=current_merchant).order_by('-created_at')

        # 获取所有平台
        all_platforms = Platform.objects.all()

        # 获取当前商家已入驻的平台（状态为approved）
        joined_platforms = Platform.objects.filter(
            enterrequest__merchant=current_merchant,
            enterrequest__status='approved'
        ).distinct()

        # 获取当前商家已申请但未入驻的平台（状态为pending）
        applied_platforms = Platform.objects.filter(
            enterrequest__merchant=current_merchant,
            enterrequest__status='pending'
        ).distinct()

        # 获取未申请的平台（排除已申请和已入驻的）
        joined_platform_ids = joined_platforms.values_list('id', flat=True)
        applied_platform_ids = applied_platforms.values_list('id', flat=True)
        not_joined_platforms = all_platforms.exclude(
            id__in=joined_platform_ids
        ).exclude(
            id__in=applied_platform_ids
        )

        # 获取当前商家的折扣设置
        platform_discounts = MerchantPlatformDiscount.objects.filter(
            merchant=current_merchant
        ).select_related('platform', 'discount').order_by('-updated_at')

        # 获取所有可用的折扣选项
        available_discounts = Discount.objects.all().order_by('discount_rate')

        # 获取当前商家的所有订单
        orders = Order.objects.filter(merchant=current_merchant).select_related(
            'customer', 'platform', 'meal', 'rider', 'discount'
        ).order_by('-created_at')

    except Merchant.DoesNotExist:
        # 如果商家信息不存在，使用空列表
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