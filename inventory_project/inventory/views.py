from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework import response
from django.core.mail import send_mail
from django.db.models import Sum, F, Q, DecimalField, ExpressionWrapper, BooleanField
from .models import Category, Supplier, Product, Order, OrderItem, User, UserToken
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.views import TokenVerifyView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework import status
from django.utils.dateparse import parse_date
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import InventoryHistory
from .serializers import (
    CategorySerializer,
    SupplierSerializer,
    ProductSerializer,
    OrderSerializer,
    DetailedOrderSerializer,
    InventoryHistorySerializer,
    InventoryReportSerializer,
    UserSerializer,
)
import logging

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ["create"]:
            return [AllowAny()]
        return [IsAuthenticated()]


# log-in views functionality
class LoginView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(username=username, password=password)

        if not user:
            return response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        print(f"Authenticated User: {user}")  # Debug statement

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Save the token in the database
        UserToken.objects.update_or_create(user=user, defaults={"token": access_token})

        return response(
            {
                "refresh": str(refresh),
                "access": access_token,
            },
            status=status.HTTP_200_OK,
        )


# log-out view Functionality
class LogoutView(APIView):
    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            # Delete the token
            token = UserToken.objects.get(user=user)
            token.delete()
            return response(
                {"message": "Logged out successfully"}, status=status.HTTP_200_OK
            )
        except UserToken.DoesNotExist:
            return response(
                {"error": "User is not logged in"}, status=status.HTTP_400_BAD_REQUEST
            )


class CategoryViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class SupplierViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated]
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ["name", "description"]  # Full-text search
    filterset_fields = ["category", "price"]  # Filters by exact match
    ordering_fields = ["name", "price", "stock_quantity"]  # Ordering

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """
        Retrieves products with stock below their threshold and sends email notifications.
        """
        # Fetch low-stock products with a threshold defined
        low_stock_products = self.queryset.filter(
            stock_quantity__lt=F("threshold")
        ).exclude(threshold=None)

        # Handle products with no threshold (default threshold = 10)
        default_low_stock_products = self.queryset.filter(
            stock_quantity__lt=10, threshold=None
        )

        # Combine results
        combined_queryset = low_stock_products | default_low_stock_products
        serializer = self.get_serializer(combined_queryset.distinct(), many=True)

        # Send low-stock email notifications
        if combined_queryset.exists():
            self.send_low_stock_email(combined_queryset)

        return Response(serializer.data)

    def send_low_stock_email(self, low_stock_products):
        """
        Sends an email notification for low-stock products.
        """
        try:
            product_names = ", ".join([product.name for product in low_stock_products])
            send_mail(
                subject="Low Stock Alert",
                message=f"The following products have low stock:\n{product_names}",
                from_email="your_email@example.com",
                recipient_list=["admin@example.com"],  # Update with actual recipients
            )
            logger.info("Low stock email sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send low stock email: {e}")

    def perform_create(self, serializer):
        product = serializer.save()
        # Log the creation as "add" action
        InventoryHistory.objects.create(
            product=product,
            user=self.request.user,
            action="add",
            quantity_changed=product.stock_quantity,
        )

    def perform_update(self, serializer):
        product = self.get_object()
        old_stock = product.stock_quantity
        new_stock = serializer.validated_data.get("stock_quantity", old_stock)
        quantity_difference = new_stock - old_stock
        action = (
            "add"
            if quantity_difference > 0
            else "remove" if quantity_difference < 0 else "update"
        )

        # Save the updated product
        updated_product = serializer.save()

        # Log the stock change
        InventoryHistory.objects.create(
            product=updated_product,
            user=self.request.user,
            action=action,
            quantity_changed=quantity_difference,
        )


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        # Ensure the user is authenticated
        if not isinstance(self.request.user, User):
            raise ValueError("Authenticated user required to fetch orders.")

        # Return orders for the authenticated user
        return Order.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return DetailedOrderSerializer
        return OrderSerializer


# Inventory history viewset
class InventoryHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    # permission_classes = [IsAuthenticated]
    queryset = InventoryHistory.objects.all().order_by("-timestamp")
    serializer_class = InventoryHistorySerializer


class ReportViewSet(viewsets.ModelViewSet):
    queryset = InventoryHistory.objects.order_by("-timestamp")
    serializer_class = InventoryReportSerializer


@action(detail=False, methods=["get"])
def inventory_report(self, request):
    # Extract date filters
    start_date = parse_date(request.query_params.get("start_date"))
    end_date = parse_date(request.query_params.get("end_date"))

    # Filter history by date range
    history_filter = Q()
    if start_date and end_date:
        history_filter &= Q(timestamp__range=(start_date, end_date))
    elif start_date:
        history_filter &= Q(timestamp__gte=start_date)
    elif end_date:
        history_filter &= Q(timestamp__lte=end_date)

    # Total Inventory Value
    total_value = (
        Product.objects.aggregate(total_value=Sum(F("price") * F("stock_quantity")))[
            "total_value"
        ]
        or 0
    )

    # Stock Levels with below_threshold annotation
    stock_levels = Product.objects.annotate(
        below_threshold=ExpressionWrapper(
            F("stock_quantity") < F("threshold"), output_field=BooleanField()
        )
    ).values("name", "stock_quantity", "threshold", "below_threshold")

    # Sales/Restocking History
    history = (
        InventoryHistory.objects.filter(history_filter)
        .order_by("-timestamp")
        .values("product__name", "action", "quantity_changed", "timestamp")
    )

    report_data = {
        "total_value": total_value,
        "stock_levels": list(stock_levels),
        "sales_history": list(history),
    }

    return response(report_data)

    # @action(
    #     detail=False,
    #     methods=["get"],
    #     url_path="inventory-report",
    #     url_name="inventory_report",
    # )
    # def inventory_report(self, request):
    #     # Extract date filters
    #     start_date_param = request.query_params.get("start_date")
    #     end_date_param = request.query_params.get("end_date")

    #     start_date = parse_date(str(start_date_param)) if start_date_param else None
    #     end_date = parse_date(str(end_date_param)) if end_date_param else None

    #     # Filter history by date range
    #     history_filter = Q()
    #     if start_date and end_date:
    #         history_filter &= Q(timestamp__range=(start_date, end_date))
    #     elif start_date:
    #         history_filter &= Q(timestamp__gte=start_date)
    #     elif end_date:
    #         history_filter &= Q(timestamp__lte=end_date)

    #     # Total Inventory Value
    #     total_value = (
    #         Product.objects.aggregate(
    #             total_value=Sum(
    #                 F("price") * F("stock_quantity"), output_field=DecimalField()
    #             )
    #         )["total_value"]
    #         or 0
    #     )

    #     # Stock Levels
    #     stock_levels = Product.objects.values(
    #         "name", "stock_quantity", "threshold"
    #     ).annotate(below_threshold=F("stock_quantity") < F("threshold"))

    #     # Sales/Restocking History
    #     history = (
    #         InventoryHistory.objects.filter(history_filter)
    #         .order_by("-timestamp")
    #         .values("product__name", "action", "quantity_changed", "timestamp")
    #     )

    #     report_data = {
    #         "total_value": total_value,
    #         "stock_levels": list(stock_levels),
    #         "sales_history": list(history),
    #     }

    #     return response(report_data)
