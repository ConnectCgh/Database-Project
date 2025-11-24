from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal

from login.models import Customer, Platform, Merchant, Rider, EnterRequest
from meal.models import Meal
from discount.models import Discount
from order.models import Order
from login.models import MerchantPlatformDiscount  # 新增导入


@login_required
def customer(request):
    """顾客主页面"""
    try:
        # 获取当前顾客
        current_customer = Customer.objects.get(user_profile__user=request.user)
        customer_name = current_customer.customer_name

        # 获取所有平台
        platforms = Platform.objects.all()

        # 获取所有商家及其入驻的平台和餐品
        merchants_with_platforms = []
        all_merchants = Merchant.objects.all()

        for merchant in all_merchants:
            # 获取商家入驻的所有平台（已批准的）
            approved_requests = EnterRequest.objects.filter(
                merchant=merchant,
                status='approved'
            ).select_related('platform')

            if approved_requests.exists():
                platforms_with_meals = []
                total_platforms = []

                for enter_request in approved_requests:
                    platform = enter_request.platform
                    total_platforms.append(platform)

                    # 获取商家在该平台下的餐品
                    meals = Meal.objects.filter(merchant=merchant, platform=platform)

                    platforms_with_meals.append({
                        'platform': platform,
                        'meals': meals,
                        'meals_count': meals.count()
                    })

                merchants_with_platforms.append({
                    'merchant': merchant,
                    'platforms': total_platforms,
                    'platforms_with_meals': platforms_with_meals
                })

        # 获取所有折扣信息（用于全局显示）
        discounts = Discount.objects.all()

        # 获取当前顾客的订单
        orders = Order.objects.filter(customer=current_customer).select_related(
            'merchant', 'platform', 'meal', 'discount', 'rider'
        ).order_by('-created_at')

    except Customer.DoesNotExist:
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
    """获取商家在特定平台下的详情和餐品信息"""
    try:
        # 验证入驻关系
        enter_request = get_object_or_404(
            EnterRequest,
            merchant_id=merchant_id,
            platform_id=platform_id,
            status='approved'
        )

        # 获取商家
        merchant = enter_request.merchant

        # 获取平台
        platform = enter_request.platform

        # 获取商家在该特定平台下的餐品
        meals = Meal.objects.filter(merchant=merchant, platform=platform)

        # 获取该商家在该平台下的可用折扣
        available_discounts = MerchantPlatformDiscount.objects.filter(
            merchant=merchant,
            platform=platform
        ).select_related('discount')

        # 序列化餐品数据
        meals_data = []
        for meal in meals:
            meals_data.append({
                'id': meal.id,
                'name': meal.name,
                'price': str(meal.price),
                'meal_type': meal.meal_type,
                'created_at': meal.created_at.strftime('%Y-%m-%d %H:%M')
            })

        # 序列化折扣数据 - 修正显示逻辑
        discounts_data = []
        for mpd in available_discounts:
            # 修正：折扣率 0.3 应该显示为 7折（支付70%）
            discount_rate = mpd.discount.discount_rate
            discount_display = f"{(1 - discount_rate) * 10:.0f}折"  # 0.3 -> 7折

            discounts_data.append({
                'id': mpd.discount.id,
                'discount_rate': str(discount_rate),  # 保持原始值 0.3
                'discount_display': discount_display  # 显示为 "7折"
            })

        return JsonResponse({
            'success': True,
            'merchant': {
                'id': merchant.id,
                'merchant_name': merchant.merchant_name,
                'phone': merchant.phone,
                'address': merchant.address
            },
            'platform': {
                'id': platform.id,
                'platform_name': platform.platform_name
            },
            'meals': meals_data,
            'available_discounts': discounts_data  # 返回可用的折扣
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'获取商家详情失败: {str(e)}'
        })


@login_required
@csrf_exempt
def place_order(request):
    """下单功能 - 需要指定平台"""
    if request.method == 'POST':
        try:
            # 获取当前顾客
            current_customer = Customer.objects.get(user_profile__user=request.user)

            # 解析请求数据
            data = json.loads(request.body)
            merchant_id = data.get('merchant_id')
            platform_id = data.get('platform_id')
            meals_data = data.get('meals', [])
            discount_id = data.get('discount_id')
            total_price = data.get('total_price')

            # 数据验证
            if not all([merchant_id, platform_id, meals_data, total_price is not None]):
                return JsonResponse({
                    'success': False,
                    'message': '缺少必要的订单信息'
                })

            # 验证商家和平台的入驻关系
            enter_request = get_object_or_404(
                EnterRequest,
                merchant_id=merchant_id,
                platform_id=platform_id,
                status='approved'
            )

            # 获取商家和平台
            merchant = enter_request.merchant
            platform = enter_request.platform

            # 获取折扣（如果选择）- 修正验证逻辑
            discount = None
            if discount_id and discount_id != '' and discount_id != 'null':
                try:
                    # 验证折扣是否适用于该商家和平台
                    mpd = MerchantPlatformDiscount.objects.get(
                        merchant=merchant,
                        platform=platform,
                        discount_id=discount_id
                    )
                    discount = mpd.discount
                except MerchantPlatformDiscount.DoesNotExist:
                    # 如果找不到对应的折扣关系，则不应用折扣
                    discount = None
                    print(
                        f"警告: 折扣 {discount_id} 不适用于商家 {merchant.merchant_name} 和平台 {platform.platform_name}")

            # 为每个选择的餐品创建订单
            created_orders = []
            for meal_data in meals_data:
                meal_id = meal_data.get('meal_id')
                quantity = meal_data.get('quantity', 1)


                # 验证餐品属于该商家和平台
                try:
                    meal = Meal.objects.get(
                        id=meal_id,
                        merchant=merchant,
                        platform=platform
                    )
                except Meal.DoesNotExist:
                    # 提供更详细的错误信息
                    available_meals = Meal.objects.filter(merchant=merchant, platform=platform)
                    available_meal_ids = list(available_meals.values_list('id', flat=True))
                    print(f"错误: 餐品 {meal_id} 不存在。可用的餐品ID: {available_meal_ids}")

                    return JsonResponse({
                        'success': False,
                        'message': f'餐品不存在或不属于该商家和平台。餐品ID: {meal_id}, 可用餐品: {available_meal_ids}'
                    })

                # 计算该餐品的价格（考虑数量和折扣）
                meal_price = meal.price * quantity
                if discount:
                    # 折扣率 0.3 表示减免30%，即支付70%
                    meal_price = meal_price * (1 - discount.discount_rate)

                # 创建订单 - 状态默认为 'unassigned' (未分配骑手)
                order = Order.objects.create(
                    customer=current_customer,
                    platform=platform,
                    merchant=merchant,
                    meal=meal,
                    discount=discount,
                    rider=None,  # 初始时没有骑手
                    price=meal_price,
                    status='unassigned'  # 修改为未分配骑手状态
                )

                created_orders.append({
                    'id': order.id,
                    'meal_name': meal.name,
                    'price': str(meal_price),
                    'status': 'unassigned'
                })

            return JsonResponse({
                'success': True,
                'message': '下单成功',
                'orders': created_orders,
                'total_price': str(total_price)
            })

        except Customer.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '顾客信息不存在'
            })
        except EnterRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '商家未入驻该平台或入驻申请未通过'
            })
        except Exception as e:
            print(f"下单异常: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'下单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def get_orders(request):
    """获取顾客的订单列表"""
    try:
        # 获取当前顾客
        current_customer = Customer.objects.get(user_profile__user=request.user)

        # 获取订单
        orders = Order.objects.filter(customer=current_customer).select_related(
            'merchant', 'platform', 'meal', 'discount', 'rider'
        ).order_by('-created_at')

        # 序列化订单数据
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order.id,
                'merchant_name': order.merchant.merchant_name,
                'platform_name': order.platform.platform_name,
                'meal_name': order.meal.name,
                'price': str(order.price),
                'discount_id': order.discount.id if order.discount else None,
                'discount_rate': str(order.discount.discount_rate * 100) if order.discount else '0',
                'rider_name': order.rider.rider_name if order.rider else None,
                'status': order.status,
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M')
            })

        return JsonResponse({
            'success': True,
            'orders': orders_data
        })

    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '顾客信息不存在'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'获取订单失败: {str(e)}'
        })


@login_required
def search_merchants(request):
    """搜索商家 - 修正为考虑多平台和餐品类型包含关系"""
    try:
        # 获取搜索参数
        platform_id = request.GET.get('platform_id')
        merchant_name = request.GET.get('merchant_name')
        meal_name = request.GET.get('meal_name')
        meal_type = request.GET.get('meal_type')

        # 构建基础查询 - 获取所有已入驻平台的商家
        approved_merchants = Merchant.objects.filter(
            enterrequest__status='approved'
        ).distinct()

        # 应用筛选条件
        if platform_id:
            approved_merchants = approved_merchants.filter(
                enterrequest__platform_id=platform_id
            )

        if merchant_name:
            approved_merchants = approved_merchants.filter(
                merchant_name__icontains=merchant_name
            )

        # 获取结果
        result_data = []
        for merchant in approved_merchants:
            # 获取商家入驻的所有平台
            approved_requests = EnterRequest.objects.filter(
                merchant=merchant,
                status='approved'
            ).select_related('platform')

            platforms_with_meals = []
            for enter_request in approved_requests:
                platform = enter_request.platform

                # 如果指定了平台筛选，跳过不匹配的平台
                if platform_id and str(platform.id) != platform_id:
                    continue

                # 获取商家在该平台下的餐品
                meals = Meal.objects.filter(merchant=merchant, platform=platform)

                # 应用餐品名称筛选条件
                if meal_name:
                    meals = meals.filter(name__icontains=meal_name)

                # 应用餐品类型筛选条件 - 处理包含关系
                if meal_type:
                    if meal_type == 'breakfast':
                        # 搜索早餐时，只显示早餐
                        meals = meals.filter(meal_type='breakfast')
                    elif meal_type == 'lunch':
                        # 搜索午餐时，显示午餐和午餐和晚餐
                        meals = meals.filter(meal_type__in=['lunch', 'lunch_and_dinner'])
                    elif meal_type == 'dinner':
                        # 搜索晚餐时，显示晚餐和午餐和晚餐
                        meals = meals.filter(meal_type__in=['dinner', 'lunch_and_dinner'])
                    elif meal_type == 'lunch_and_dinner':
                        # 搜索午餐和晚餐时，显示午餐、晚餐和午餐和晚餐
                        meals = meals.filter(meal_type__in=['lunch', 'dinner', 'lunch_and_dinner'])

                # 序列化餐品数据
                meals_data = []
                for meal in meals:
                    meals_data.append({
                        'id': meal.id,
                        'name': meal.name,
                        'price': str(meal.price),
                        'meal_type': meal.meal_type
                    })

                # 只有当有餐品时才显示该平台
                if meals.exists() or (not meal_name and not meal_type):
                    platforms_with_meals.append({
                        'platform': {
                            'id': platform.id,
                            'platform_name': platform.platform_name
                        },
                        'meals': meals_data,
                        'meals_count': meals.count()
                    })

            # 只有当商家有平台时才显示
            if platforms_with_meals:
                result_data.append({
                    'merchant': {
                        'id': merchant.id,
                        'merchant_name': merchant.merchant_name,
                        'phone': merchant.phone,
                        'address': merchant.address
                    },
                    'platforms_with_meals': platforms_with_meals
                })

        return JsonResponse({
            'success': True,
            'merchants': result_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'搜索失败: {str(e)}'
        })


@login_required
@csrf_exempt
def delete_order(request, order_id):
    """删除订单"""
    if request.method == 'DELETE':
        try:
            # 获取当前顾客
            current_customer = Customer.objects.get(user_profile__user=request.user)

            # 获取订单并验证属于当前顾客
            order = get_object_or_404(Order, id=order_id, customer=current_customer)

            # 检查订单状态，只有未分配骑手或已取消的订单可以删除
            if order.status not in ['unassigned', 'cancelled']:
                return JsonResponse({
                    'success': False,
                    'message': '只能删除未分配骑手或已取消的订单'
                })

            # 删除订单
            order.delete()

            return JsonResponse({
                'success': True,
                'message': '订单删除成功'
            })

        except Customer.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '顾客信息不存在'
            })
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '订单不存在或不属于当前顾客'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'删除订单失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
@csrf_exempt
def pickup_order(request, order_id):
    """取餐功能 - 删除状态为'ready'的订单"""
    if request.method == 'POST':
        try:
            # 获取当前顾客
            current_customer = Customer.objects.get(user_profile__user=request.user)

            # 获取订单并验证属于当前顾客
            order = get_object_or_404(Order, id=order_id, customer=current_customer)

            # 检查订单状态，只有'ready'状态的订单可以取餐
            if order.status != 'ready':
                return JsonResponse({
                    'success': False,
                    'message': '只能取餐状态为"待取餐"的订单'
                })

            # 记录订单信息（可选，用于日志或统计）
            order_info = {
                'id': order.id,
                'customer': order.customer.customer_name,
                'merchant': order.merchant.merchant_name,
                'meal': order.meal.name,
                'price': str(order.price),
                'status': order.status
            }

            # 删除订单
            order.delete()

            # 记录取餐日志（可选）
            print(f"顾客 {current_customer.customer_name} 取餐完成，订单 {order_id} 已删除")

            return JsonResponse({
                'success': True,
                'message': '取餐成功，订单已删除',
                'order_info': order_info
            })

        except Customer.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '顾客信息不存在'
            })
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '订单不存在或不属于当前顾客'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'取餐失败: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '无效的请求方法'})