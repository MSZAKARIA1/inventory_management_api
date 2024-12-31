from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

# from .models import Product


User = get_user_model()


# Custom User model
class RoleChoices(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"


class User(AbstractUser):
    role = models.CharField(
        max_length=10, choices=RoleChoices.choices, default=RoleChoices.STAFF
    )

    # Override groups and user_permissions with unique related_name
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="custom_user_set",  # Unique related_name to avoid conflict
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="custom_user_permissions_set",  # Unique related_name to avoid conflict
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"



#  Token generation model
class UserToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="token")
    token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token for {self.user.username}"



class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name.title()

    class Meta:
        ordering = ["name"]


class Supplier(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(default="zakariamahamasaani@gmail.com")
    address = models.TextField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    threshold = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0)],
        help_text="Reorder level. Default is 10.",
    )
    # reorder_level = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_below_threshold(self):
        """Check if stock quantity is below the threshold."""
        return self.stock_quantity < self.threshold

    def clean(self):
        """Ensure threshold is valid."""
        if self.threshold < 0:
            raise ValidationError(
                {"threshold": "Threshold must be a non-negative value."}
            )

    def save(self, *args, **kwargs):
        """Validate threshold before saving."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Order(models.Model):
    class OrderTypeChoices(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    order_type = models.CharField(max_length=10, choices=OrderTypeChoices.choices)
    status = models.CharField(
        max_length=10, choices=StatusChoices.choices, default=StatusChoices.PENDING
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Calculate total_amount only for new orders
            self.total_amount = sum(
                item.price_at_purchase * item.quantity for item in self.items.all()
            )
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1.00)])
    price_at_purchase = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.00)]
    )

    def save(self, *args, **kwargs):
        if self.quantity > self.product.stock_quantity:
            raise ValueError("Insufficient stock for this product.")
        self.product.stock_quantity -= self.quantity
        self.product.save()
        super().save(*args, **kwargs)


class InventoryHistory(models.Model):
    ACTION_CHOICES = [
        ("add", "Add Stock"),
        ("remove", "Remove Stock"),
        ("update", "Update Product"),
    ]
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="history"
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    quantity_changed = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]  # Default ordering by timestamp descending

    def __str__(self):
        user_name = self.user.username if self.user else "System"
        return f"{self.product.name} - {self.action} by {user_name}"
