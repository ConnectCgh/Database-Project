# meal/models.py
from django.db import models
from login.models import Merchant, Platform


class Meal(models.Model):
    MEAL_TYPE_CHOICES = [
        ('breakfast', '早餐'),
        ('lunch', '午餐'),
        ('dinner', '晚餐'),
        ('lunch_and_dinner', '午餐和晚餐'),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, verbose_name="平台")
    name = models.CharField(max_length=100, verbose_name="餐品名称")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, verbose_name="餐品类型")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meal'

    def __str__(self):
        return f"{self.name} - ¥{self.price}"