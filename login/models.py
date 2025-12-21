# models.py
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from discount.models import Discount
from Project.db_utils import execute_fetchone, execute_non_query, execute_write

PLACEHOLDER_ADDRESS = '待填写'


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


def _clean_text(value, default=''):
    return value if value is not None else default


def _ensure_customer_record(profile_id, name, phone):
    if not profile_id:
        return
    existing = execute_fetchone('SELECT id FROM customer WHERE user_profile_id = %s', [profile_id])
    if existing:
        return
    now = timezone.now()
    execute_write(
        '''
        INSERT INTO customer (user_profile_id, customer_name, phone, address, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        [profile_id, _clean_text(name), _clean_text(phone), PLACEHOLDER_ADDRESS, now],
    )


def _ensure_rider_record(profile_id, name, phone):
    if not profile_id:
        return
    existing = execute_fetchone('SELECT id FROM rider WHERE user_profile_id = %s', [profile_id])
    if existing:
        return
    now = timezone.now()
    execute_write(
        '''
        INSERT INTO rider (user_profile_id, rider_name, phone, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        [profile_id, _clean_text(name), _clean_text(phone), 'offline', now],
    )


def _ensure_merchant_record(profile_id, name, phone):
    if not profile_id:
        return
    existing = execute_fetchone('SELECT id FROM merchant WHERE user_profile_id = %s', [profile_id])
    if existing:
        return
    now = timezone.now()
    execute_write(
        '''
        INSERT INTO merchant (user_profile_id, merchant_name, phone, address, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        [profile_id, _clean_text(name), _clean_text(phone), PLACEHOLDER_ADDRESS, now],
    )


def _ensure_platform_record(profile_id, name, phone):
    if not profile_id:
        return
    existing = execute_fetchone('SELECT id FROM platform WHERE user_profile_id = %s', [profile_id])
    if existing:
        return
    now = timezone.now()
    execute_write(
        '''
        INSERT INTO platform (user_profile_id, platform_name, phone, created_at)
        VALUES (%s, %s, %s, %s)
        ''',
        [profile_id, _clean_text(name), _clean_text(phone), now],
    )


def _ensure_role_records(profile_id, user_type, username, phone):
    if user_type == 'customer':
        _ensure_customer_record(profile_id, username, phone)
    elif user_type == 'rider':
        _ensure_rider_record(profile_id, username, phone)
    elif user_type == 'merchant':
        _ensure_merchant_record(profile_id, username, phone)
    elif user_type == 'platform':
        _ensure_platform_record(profile_id, username, phone)


def _get_username_by_id(user_id):
    if not user_id:
        return ''
    record = execute_fetchone('SELECT username FROM auth_user WHERE id = %s', [user_id])
    return record['username'] if record else ''


def _ensure_user_profile_record(user):
    if not user or not user.id:
        return None
    profile = execute_fetchone(
        'SELECT id, user_type, phone FROM user_profile WHERE user_id = %s',
        [user.id],
    )
    if profile:
        execute_non_query(
            'UPDATE user_profile SET updated_at = %s WHERE id = %s',
            [timezone.now(), profile['id']],
        )
        return profile

    now = timezone.now()
    profile_id = execute_write(
        '''
        INSERT INTO user_profile (user_id, user_type, phone, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ''',
        [user.id, 'customer', '', now, now],
    )
    _ensure_role_records(profile_id, 'customer', user.username, '')
    return {'id': profile_id, 'user_type': 'customer', 'phone': ''}


# 信号处理：根据用户类型创建对应的详细表
@receiver(post_save, sender=UserProfile)
def create_user_type_profile(sender, instance, created, **kwargs):
    if not created:
        return
    username = _get_username_by_id(instance.user_id)
    _ensure_role_records(instance.id, instance.user_type, username, instance.phone or '')


@receiver(post_save, sender=UserProfile)
def save_user_type_profile(sender, instance, **kwargs):
    username = _get_username_by_id(instance.user_id)
    _ensure_role_records(instance.id, instance.user_type, username, instance.phone or '')

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """创建用户时自动创建 UserProfile"""
    if created:
        _ensure_user_profile_record(instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """保存用户时确保 UserProfile 存在"""
    _ensure_user_profile_record(instance)
