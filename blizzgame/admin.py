from django.contrib import admin

from blizzgame.models import (
    Post, PostImage, PostVideo, Profile, Product, ProductCategory, 
    ProductImage, ProductVariant, Order, OrderItem, Cart, CartItem,
    ShopCinetPayTransaction, ShopifyIntegration, UserReputation
)

# Modèles existants
admin.site.register(Profile)
admin.site.register(Post)
admin.site.register(PostImage)
admin.site.register(PostVideo)
admin.site.register(UserReputation)

# === ADMINISTRATION BOUTIQUE E-COMMERCE ===

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active']

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'order']

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['name', 'value', 'price_adjustment', 'shopify_variant_id', 'is_active']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'status', 'is_featured', 'shopify_product_id', 'created_at']
    list_filter = ['status', 'is_featured', 'category', 'created_at']
    search_fields = ['name', 'description', 'shopify_product_id']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['status', 'is_featured', 'price']
    inlines = [ProductImageInline, ProductVariantInline]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('name', 'slug', 'category', 'description', 'short_description')
        }),
        ('Prix et statut', {
            'fields': ('price', 'compare_price', 'cost_price', 'status', 'is_featured')
        }),
        ('Médias', {
            'fields': ('featured_image',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'tags'),
            'classes': ('collapse',)
        }),
        ('Shopify', {
            'fields': ('shopify_product_id', 'shopify_variant_id', 'shopify_handle'),
            'classes': ('collapse',)
        }),
    )

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_name', 'product_price', 'quantity', 'total_price']
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer_email', 'total_amount', 'status', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_status', 'shipping_country', 'created_at']
    search_fields = ['order_number', 'customer_email', 'customer_first_name', 'customer_last_name']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    list_editable = ['status']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Informations de commande', {
            'fields': ('order_number', 'user', 'status', 'payment_status')
        }),
        ('Client', {
            'fields': ('customer_first_name', 'customer_last_name', 'customer_email', 'customer_phone')
        }),
        ('Adresse de livraison', {
            'fields': ('shipping_address_line1', 'shipping_address_line2', 'shipping_city', 
                      'shipping_state', 'shipping_postal_code', 'shipping_country')
        }),
        ('Montants', {
            'fields': ('subtotal', 'shipping_cost', 'tax_amount', 'total_amount')
        }),
        ('Shopify', {
            'fields': ('shopify_order_id', 'shopify_order_number', 'shopify_fulfillment_status'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ShopCinetPayTransaction)
class ShopCinetPayTransactionAdmin(admin.ModelAdmin):
    list_display = ['cinetpay_transaction_id', 'order', 'customer_email', 'amount', 'status', 'created_at']
    list_filter = ['status', 'currency', 'customer_country', 'created_at']
    search_fields = ['cinetpay_transaction_id', 'customer_email', 'order__order_number']
    readonly_fields = ['cinetpay_transaction_id', 'payment_url', 'payment_token', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Transaction', {
            'fields': ('cinetpay_transaction_id', 'order', 'status', 'amount', 'currency')
        }),
        ('Client', {
            'fields': ('customer_name', 'customer_surname', 'customer_email', 
                      'customer_phone_number', 'customer_country')
        }),
        ('CinetPay', {
            'fields': ('payment_url', 'payment_token'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ShopifyIntegration)
class ShopifyIntegrationAdmin(admin.ModelAdmin):
    list_display = ['shop_name', 'shop_url', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['shop_name', 'shop_url']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Configuration Shopify', {
            'fields': ('shop_name', 'shop_url', 'access_token', 'is_active')
        }),
        ('Webhooks', {
            'fields': ('webhook_secret',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )