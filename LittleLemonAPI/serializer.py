from rest_framework import serializers
from .models import MenuItem, Category, Cart, Order, OrderItem
from rest_framework.validators import UniqueTogetherValidator
from django.contrib.auth.models import User

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['slug', 'title']
    
class MenuItemSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field='slug', queryset=Category.objects.all())
    
    class Meta:
        model = MenuItem
        fields = ['id', 'title', 'price', 'category', 'featured']
        validators = [
            UniqueTogetherValidator(
                queryset=MenuItem.objects.all(),
                fields=['title', 'category'],
                message="A menu item with this title already exists in this category."
            )
        ]

class CartSerializer(serializers.ModelSerializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    
    class Meta:
        model = Cart
        fields = ['id', 'user', 'menu_item', 'quantity', 'unit_price', 'price']
        read_only_fields = ['user', 'unit_price', 'price']
    
    def validate(self, attrs):
        menu_item = attrs.get('menu_item')
        quantity = attrs.get('quantity', 1)
        
        if not menu_item and self.instance:
            menu_item = self.instance.menu_item
        if not quantity and self.instance:
            quantity = self.instance.quantity

        if menu_item and quantity:
            unit_price = menu_item.price
            total_price = menu_item.price * quantity
            attrs['price'] = total_price
        else:
            raise serializers.ValidationError("Menu item and quantity must be provided.")
        return attrs

class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = serializers.PrimaryKeyRelatedField(queryset=MenuItem.objects.all())
    
    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'menu_item', 'quantity', 'unit_price', 'price']
        read_only_fields = ['order', 'unit_price', 'price']

class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'user', 'total', 'Date', 'status', 'delivery_crew', 'order_items']
        read_only_fields = ['user', 'total', 'Date']

    def validate_delivery_crew(self, value):
        if value and not value.groups.filter(name='Delivery Crew').exists():
            raise serializers.ValidationError("Assigned delivery crew must be a user in the 'Delivery Crew' group.")
        return value

class DeliveryCrewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']
    def validate_status(self, value):
        if not isinstance(value, bool):
            raise serializers.ValidationError("Status must be a boolean value.")
        return value