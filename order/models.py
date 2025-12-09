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
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, verbose_name="餐品")
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


class OrderRating(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='rating')
    merchant_rating = models.DecimalField(max_digits=3, decimal_places=2)
    meal_rating = models.DecimalField(max_digits=3, decimal_places=2)
    platform_rating = models.DecimalField(max_digits=3, decimal_places=2)
    rider_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_rating'
        verbose_name = '订单评分'
        verbose_name_plural = '订单评分'
