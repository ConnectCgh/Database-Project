# discount/models.py
from django.db import models

class Discount(models.Model):
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="打折比例")

    class Meta:
        db_table = 'discount'
        verbose_name = '折扣'
        verbose_name_plural = '折扣'

    def __str__(self):
        return f"折扣ID: {self.id} - 打折比例: {self.discount_rate}%"