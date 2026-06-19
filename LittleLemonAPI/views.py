from urllib import request

from django.shortcuts import render

# Create your views here.
from rest_framework import generics
from .models import MenuItem, Category, Cart, Order, OrderItem
from .serializer import MenuItemSerializer, CategorySerializer, CartSerializer, OrderSerializer, OrderItemSerializer, DeliveryCrewOrderUpdateSerializer
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import BasePermission, SAFE_METHODS, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.contrib.auth.models import User, Group
from rest_framework.views import APIView

class IsManagerOrAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # Safe methods (GET, HEAD, OPTIONS) are always allowed
        if request.method in SAFE_METHODS:
            return True
        
        # Modification methods require authentication
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only superusers or Managers can modify
        return request.user.is_superuser or request.user.groups.filter(name='Manager').exists()
    
class MenuItemListCreateView(generics.ListCreateAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]
    pagination_class = PageNumberPagination
    ordering_fields = ['price']
    filterset_fields = ['category']
    ordering = ['id']  # Default ordering by id

class MenuItemRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]

class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]
    ordering_fields = ['title']
    ordering = ['title']  # Default ordering by title  

class CategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrAdminOrReadOnly]

class CartListCreateView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({"detail": "No items in cart to delete."}, status=status.HTTP_400_BAD_REQUEST)
        queryset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.groups.filter(name='Manager').exists():
            return Order.objects.all()
        if user.groups.filter(name='Delivery Crew').exists():
            return Order.objects.filter(delivery_crew=user)
        return Order.objects.filter(user=user)
    
    def get_serializer_class(self):
        user = self.request.user
        if user.groups.filter(name='Manager').exists() and self.action in ['update', 'partial_update']:
            return DeliveryCrewOrderUpdateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        user = request.user

        # Prevent Managers and Delivery Crew from placing orders
        if user.groups.filter(name__in=['Manager', 'Delivery Crew']).exists():
            return Response(
                {"detail": "Staff and managers cannot place customer orders."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fetch current user's cart items
        cart_items = CartItem.objects.filter(user=user)
        if not cart_items.exists():
            return Response(
                {"detail": "Your cart is empty. Cannot place an order."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomic transaction ensures everything succeeds together, or nothing does
        with transaction.atomic():
            # Calculate grand total from cart items
            grand_total = sum(item.price for item in cart_items)

            # Create the master Order instance
            order = Order.objects.create(
                user=user,
                total=grand_total,
                status=0 # Default status (e.g., Pending/Received)
            )

            # Loop through cart items and copy them to Order Items
            order_items_to_create = []
            for cart_item in cart_items:
                order_items_to_create.append(
                    OrderItem(
                        order=order,
                        menuitem=cart_item.menuitem,
                        quantity=cart_item.quantity,
                        price=cart_item.price # Stores computed price at purchase time
                    )
                )
            OrderItem.objects.bulk_create(order_items_to_create)

            # Wipe the user's cart completely clean
            cart_items.delete()

        # Serialize and return the newly generated order
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    def update(self, request, *args, **kwargs):
        user = request.user
        
        # Block regular customers from trying to PUT/PATCH any order
        is_manager = user.groups.filter(name='Manager').exists() or user.is_superuser
        is_delivery = user.groups.filter(name='Delivery Crew').exists()
        
        if not (is_manager or is_delivery):
            return Response(
                {"detail": "Customers are not allowed to modify orders."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().update(request, *args, **kwargs)
    

class DeliveryCrewManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def check_manager_permission(self, request):
        """Helper to ensure only managers/superusers access this endpoint."""
        if not (request.user.is_superuser or request.user.groups.filter(name='Manager').exists()):
            return False
        return True

    def post(self, request):
        """
        POST /api/groups/delivery-crew/users
        Payload example: {"username": "john_doe"}
        """
        if not self.check_manager_permission(request):
            return Response({"detail": "You do not have permission to manage groups."}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        if not username:
            return Response({"detail": "Username field is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Fetch the user
            user_to_add = User.objects.get(username=username)
            # 2. Fetch (or automatically create) the 'Delivery Crew' group
            delivery_crew_group, created = Group.objects.get_or_create(name='Delivery Crew')
            
            # 3. Add the user to the group
            user_to_add.groups.add(delivery_crew_group)
            
            return Response({"detail": f"User '{username}' successfully added to Delivery Crew."}, status=status.HTTP_201_CREATED)
            
        except User.DoesNotExist:
            return Response({"detail": f"User '{username}' not found."}, status=status.HTTP_404_NOT_FOUND)