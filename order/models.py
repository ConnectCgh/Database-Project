# order/models.py
from django.db import models
from login.models import Customer, Platform, Merchant, Rider
from meal.models import Meal
from discount.models import Discount

class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('unassigned', '未分配骑手'),
        ('assigned', '已分配骑手'),
        ('ready', '顾客待取餐'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, verbose_name="顾客")
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, verbose_name="平台")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, verbose_name="商家")
    discount = models.ForeignKey(Discount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="折扣")
    rider = models.ForeignKey(Rider, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="骑手")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending', verbose_name="订单状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'order'
        verbose_name = '订单'
        verbose_name_plural = '订单'

    def __str__(self):
        return f"订单 {self.id} - {self.customer.customer_name} - ¥{self.price}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="订单")
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, verbose_name="餐品")
    quantity = models.PositiveIntegerField(default=1, verbose_name="数量")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="单价")
    line_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="小计")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'order_item'
        verbose_name = '订单餐品'
        verbose_name_plural = '订单餐品'

    def __str__(self):
        return f"订单{self.order_id} - {self.meal.name} x {self.quantity}"


class OrderRating(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='rating')
    merchant_rating = models.DecimalField(max_digits=3, decimal_places=2)
    platform_rating = models.DecimalField(max_digits=3, decimal_places=2)
    rider_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_rating'
        verbose_name = '订单评分'
        verbose_name_plural = '订单评分'


class OrderMealRating(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='meal_ratings', verbose_name="订单")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='meal_ratings', verbose_name="订单餐品")
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, verbose_name="餐品")
    rating = models.DecimalField(max_digits=3, decimal_places=2, verbose_name="餐品评分")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_meal_rating'
        verbose_name = '餐品评分'
        verbose_name_plural = '餐品评分'
