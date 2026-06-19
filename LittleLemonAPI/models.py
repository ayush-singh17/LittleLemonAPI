from django.db import models

# Create your models here.
class Category(models.Model):
    slug = models.SlugField(primary_key=True)
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title
    
class MenuItem(models.Model):
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='menu_items')
    featured = models.BooleanField(default=False)

    def __str__(self):
        return self.title   
    
class Cart(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='cart_items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    class Meta:
        unique_together = ('user', 'menu_item')

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.title} for {self.user.username}"
    
class Order(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='orders')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    Date = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(default=False)  # False for out of delivery, True for delivered
    delivery_crew = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)
    price = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = ('order', 'menu_item')

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.title} for Order {self.order.id}"