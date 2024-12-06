from django.db import models
from django.contrib.auth.models import AbstractUser


# Custom User model

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("staff", "Staff"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="staff")

    # Existing custom fields can go here if needed
    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="custom_user_set",  # Unique related_name
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="custom_user_permissions_set",  # Unique related_name
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )


# class User(AbstractUser):
#     ROLE_CHOICES = [
#         ("admin", "Admin"),
#         ("staff", "Staff"),
#     ]
#     role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="staff")


class Category(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    contact_info = models.JSONField()
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    ORDER_TYPE_CHOICES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
    ]
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.IntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
