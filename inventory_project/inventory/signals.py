from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Product


@receiver(post_save, sender=Product)
def notify_low_stock(sender, instance, **kwargs):
    if instance.is_below_threshold():
        send_mail(
            subject="Low Stock Alert",
            message=f"The product '{instance.name}' has low stock. Current stock: {instance.stock_quantity}.",
            from_email="your_email@example.com",
            recipient_list=["admin@example.com"],  # Replace with recipients
        )
     