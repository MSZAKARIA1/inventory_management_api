from rest_framework import serializers
from django.db.models import Sum, F, DecimalField
from decimal import Decimal
from .models import (
    User,
    Category,
    Supplier,
    Product,
    Order,
    OrderItem,
    InventoryHistory,
)
from django.contrib.auth.models import User
from rest_framework import serializers


# User serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"

    def validate_contact_info(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Contact info must be a JSON object.")
        if "email" not in value or "phone" not in value:
            raise serializers.ValidationError(
                "Contact info must include 'email' and 'phone'."
            )
        return value


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(read_only=True, slug_field="name")
    is_below_threshold = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def get_is_below_threshold(self, obj):
        # Return whether the stock quantity is below the threshold
        return obj.is_below_threshold()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class DetailedOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True, read_only=True
    )  # Include related order items
    user = (
        serializers.StringRelatedField()
    )  # Optionally represent user as a string (e.g., username)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_type",
            "status",
            "total_amount",
            "user",
            "items",
            "created_at",
            "updated_at",
        ]


# oder serializer
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create order items
        for item_data in items_data:
            OrderItem.objects.update_or_create(
                order=instance,
                product=item_data["product"],
                defaults={
                    "quantity": item_data["quantity"],
                    "price_at_purchase": item_data["price_at_purchase"],
                },
            )
        return instance


# inventory History Serializer
class InventoryHistorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = InventoryHistory
        fields = [
            "id",
            "product_name",
            "user_name",
            "action",
            "quantity_changed",
            "timestamp",
        ]

    # Reorder serializer


class ReorderSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "stock_quantity", "reorder_level"]


class InventoryReportSerializer(serializers.ModelSerializer):
    total_inventory_value = serializers.SerializerMethodField()
    total_stock_levels = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = InventoryHistory
        fields = ["total_inventory_value", "total_stock_levels", "history"]

    def get_total_inventory_value(self, obj):
        # Calculate the total inventory value
        total_value = Product.objects.aggregate(
            total_value=Sum(
                F("price") * F("stock_quantity"), output_field=DecimalField()
            )
        )["total_value"]
        return total_value or 0

    def get_total_stock_levels(self, obj):
        # Calculate the total stock levels
        total_stock = Product.objects.aggregate(total_stock=Sum("stock_quantity"))[
            "total_stock"
        ]
        return total_stock or 0

    def get_history(self, obj):
        # Include sales/restocking history
        history = InventoryHistory.objects.order_by("-timestamp")
        return [
            {
                "product": record.product.name,
                "action": record.action,
                "quantity_changed": record.quantity_changed,
                "user": record.user.username if record.user else "N/A",
                "timestamp": record.timestamp,
            }
            for record in history
        ]
