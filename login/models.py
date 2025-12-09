# models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from discount.models import Discount


class UserProfile(models.Model):
    USER_TYPE_CHOICES = [
        ('customer', '顾客'),
        ('rider', '骑手'),
        ('merchant', '商家'),
        ('platform', '平台'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='userprofile'
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profile'

    def __str__(self):
        return f"{self.user.username} ({self.get_user_type_display()})"

# 顾客表 - 顾客名，电话，地址
class Customer(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)  # 顾客名
    phone = models.CharField(max_length=15)  # 电话
    address = models.TextField()  # 地址
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer'

    def __str__(self):
        return f"顾客: {self.customer_name}"

# 商家表 - 商家名，电话，地址
class Merchant(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    merchant_name = models.CharField(max_length=100)  # 商家名
    phone = models.CharField(max_length=15)  # 电话
    address = models.TextField()  # 地址
    created_at = models.DateTimeField(auto_now_add=True)
    rating_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'merchant'

    def __str__(self):
        return f"商家: {self.merchant_name}"

# 平台表 - 平台名，电话
class Platform(models.Model):
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    platform_name = models.CharField(max_length=100)  # 平台名
    phone = models.CharField(max_length=15)  # 电话
    created_at = models.DateTimeField(auto_now_add=True)
    rating_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'platform'

    def __str__(self):
        return f"平台: {self.platform_name}"

# 骑手表 - 骑手名，电话，状态
class Rider(models.Model):
    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '离线'),
        ('busy', '忙碌'),
        ('resting', '休息中'),
    ]

    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    rider_name = models.CharField(max_length=100)  # 骑手名
    phone = models.CharField(max_length=15)  # 电话
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')  # 状态
    created_at = models.DateTimeField(auto_now_add=True)
    rating_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'rider'

    def __str__(self):
        return f"骑手: {self.rider_name}"

class EnterRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝')
    ]

    merchant = models.ForeignKey('Merchant', on_delete=models.CASCADE, verbose_name='商家')
    platform = models.ForeignKey('Platform', on_delete=models.CASCADE, verbose_name='平台')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='审核状态')

    class Meta:
        db_table = 'enter_request'
        verbose_name = '入驻申请'
        verbose_name_plural = '入驻申请'
        unique_together = ['merchant', 'platform']  # 防止重复申请

    def __str__(self):
        return f"{self.merchant.merchant_name} 申请入驻 {self.platform.platform_name}"

class SignRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝')
    ]

    rider = models.ForeignKey('Rider', on_delete=models.CASCADE, verbose_name='骑手')
    platform = models.ForeignKey('Platform', on_delete=models.CASCADE, verbose_name='平台')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='审核状态')

    class Meta:
        db_table = 'sign_request'
        verbose_name = '签约申请'
        verbose_name_plural = '签约申请'
        unique_together = ['rider', 'platform']  # 防止重复申请

    def __str__(self):
        return f"{self.rider.rider_name} 申请签约 {self.platform.platform_name}"

class MerchantPlatformDiscount(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, verbose_name='商家')
    platform = models.ForeignKey(Platform, on_delete=models.CASCADE, verbose_name='平台')
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, verbose_name='折扣')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'merchant_platform_discount'
        verbose_name = '商家平台折扣'
        verbose_name_plural = '商家平台折扣'
        unique_together = ['merchant', 'platform']  # 确保每个商家在每个平台上只有一个折扣

    def __str__(self):
        return f"{self.merchant.merchant_name} 在 {self.platform.platform_name} 的折扣: {self.discount.discount_rate}%"

# 信号处理：根据用户类型创建对应的详细表
@receiver(post_save, sender=UserProfile)
def create_user_type_profile(sender, instance, created, **kwargs):
    if created:
        # 使用用户名作为默认的名称
        default_name = instance.user.username

        if instance.user_type == 'customer':
            Customer.objects.create(
                user_profile=instance,
                customer_name=default_name,
                phone=instance.phone or ''
            )
        elif instance.user_type == 'rider':
            Rider.objects.create(
                user_profile=instance,
                rider_name=default_name,
                phone=instance.phone or ''
            )
        elif instance.user_type == 'merchant':
            Merchant.objects.create(
                user_profile=instance,
                merchant_name=default_name,
                phone=instance.phone or ''
            )
        elif instance.user_type == 'platform':
            Platform.objects.create(
                user_profile=instance,
                platform_name=default_name,
                phone=instance.phone or ''
            )


@receiver(post_save, sender=UserProfile)
def save_user_type_profile(sender, instance, **kwargs):
    # 确保关联表也存在
    if instance.user_type == 'customer' and not hasattr(instance, 'customer'):
        Customer.objects.create(
            user_profile=instance,
            customer_name=instance.user.username,
            phone=instance.phone or ''
        )
    elif instance.user_type == 'rider' and not hasattr(instance, 'rider'):
        Rider.objects.create(
            user_profile=instance,
            rider_name=instance.user.username,
            phone=instance.phone or ''
        )
    elif instance.user_type == 'merchant' and not hasattr(instance, 'merchant'):
        Merchant.objects.create(
            user_profile=instance,
            merchant_name=instance.user.username,
            phone=instance.phone or ''
        )
    elif instance.user_type == 'platform' and not hasattr(instance, 'platform'):
        Platform.objects.create(
            user_profile=instance,
            platform_name=instance.user.username,
            phone=instance.phone or ''
        )

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """创建用户时自动创建 UserProfile"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """保存用户时确保 UserProfile 存在"""
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
