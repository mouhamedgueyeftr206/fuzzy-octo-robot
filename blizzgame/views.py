from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.core.exceptions import ValidationError
import json
import logging

from .models import (
    Profile, Post, PostImage, PostVideo, Transaction, Chat, Message, Notification,
    Product, ProductCategory, Cart, CartItem, Order, OrderItem, ShopCinetPayTransaction,
    ProductVariant, UserReputation, SellerPaymentInfo, Highlight, HighlightLike, 
    HighlightComment, HighlightView, HighlightShare, UserSubscription
)
from .shopify_utils import create_shopify_order_from_blizz_order, sync_products_from_shopify
from .cinetpay_utils import CinetPayAPI, handle_cinetpay_notification, convert_currency_for_cinetpay
from django.db.models import Exists, OuterRef
import re

logger = logging.getLogger(__name__)

# ===== Vues existantes simples (stubs pour garantir l'import) =====

def index(request):
	posts = Post.objects.all().order_by('-created_at')[:20]
	return render(request, 'index.html', {'posts': posts})

def profile(request, username):
    user = get_object_or_404(User, username=username)
    prof = getattr(user, 'profile', None)
    user_posts = Post.objects.filter(author=user).order_by('-created_at')
    return render(request, 'profile.html', {'profile': prof, 'user_obj': user, 'posts': user_posts})

@login_required
def settings(request):
    if request.method == 'POST':
        prof = request.user.profile
        prof.bio = request.POST.get('bio', prof.bio)
        prof.location = request.POST.get('location', prof.location)
        prof.save()
        messages.success(request, 'Profil mis à jour')
        return redirect('settings')
    return render(request, 'settings.html')

@login_required
def create(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'sans nom')
        caption = request.POST.get('caption', '')
        price = request.POST.get('price', '0')
        post = Post.objects.create(user=request.user.username, author=request.user, title=title, caption=caption, price=price)
        return redirect('product_detail', post_id=post.id)
    return render(request, 'create.html')

def product_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'product_detail.html', {'post': post})

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    return redirect('index')

def logout_view(request):
    logout(request)
    return redirect('index')

# ===== Transactions gaming (stubs minimaux) =====

@login_required
def initiate_transaction(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    transaction = Transaction.objects.create(buyer=request.user, seller=post.author, post=post, amount=post.price)
    return redirect('transaction_detail', transaction_id=transaction.id)

@login_required
def transaction_detail(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    return render(request, 'cinetpay_payment_form.html', {'transaction': transaction})

@login_required
def transaction_list(request):
    txs = Transaction.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).order_by('-created_at')
    return render(request, 'notifications.html', {'transactions': txs})

@login_required
def confirm_reception(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, buyer=request.user)
    transaction.status = 'completed'
    transaction.completed_at = timezone.now()
    transaction.save()
    messages.success(request, 'Réception confirmée')
    return redirect('transaction_detail', transaction_id=transaction.id)

# ===== CinetPay pour transactions gaming existantes (stubs) =====

@login_required
def initiate_cinetpay_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    return render(request, 'cinetpay_payment_form.html', {'transaction': transaction})

@csrf_exempt
def cinetpay_notification(request):
    return HttpResponse('OK', status=200)

def cinetpay_payment_success(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    transaction.status = 'completed'
    transaction.save()
    return render(request, 'cinetpay_success.html', {'transaction': transaction})

def cinetpay_payment_failed(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    transaction.status = 'failed'
    transaction.save()
    return render(request, 'cinetpay_failed.html', {'transaction': transaction})

# ===== Chat, notifications et amis (stubs basiques pour éviter les erreurs d'import) =====

def chat_home(request):
    return render(request, 'chat/chat_home.html')

def chat_list(request):
    return render(request, 'chat_list.html')

def notifications(request):
    notes = Notification.objects.filter(user=request.user) if request.user.is_authenticated else []
    return render(request, 'notifications.html', {'notifications': notes})

def mark_notification_read(request, notification_id):
    note = get_object_or_404(Notification, id=notification_id, user=request.user)
    note.is_read = True
    note.save()
    return redirect('notifications')

def user_search(request):
    q = request.GET.get('q', '')
    users = User.objects.filter(username__icontains=q)[:20]
    return render(request, 'chat/user_search.html', {'users': users})

def private_chat(request, user_id):
    other = get_object_or_404(User, id=user_id)
    return render(request, 'chat/private_chat.html', {'other': other})

@require_POST
def send_private_message(request, conversation_id):
    return JsonResponse({'success': True})

def get_private_messages(request, conversation_id):
    return JsonResponse({'messages': []})

def group_list(request):
    return render(request, 'chat/group_list.html')

@login_required
def create_group(request):
    return render(request, 'chat/create_group.html')

def group_chat(request, group_id):
    return render(request, 'chat/group_chat.html')

def send_group_message(request, group_id):
    return JsonResponse({'success': True})

def get_group_messages(request, group_id):
    return JsonResponse({'messages': []})

def group_members(request, group_id):
    return render(request, 'chat/group_members.html')

def group_settings(request, group_id):
    return render(request, 'chat/group_settings.html')

def add_group_member(request, group_id):
    return JsonResponse({'success': True})

def remove_group_member(request, group_id):
    return JsonResponse({'success': True})

def promote_member(request, group_id):
    return JsonResponse({'success': True})

def leave_group(request, group_id):
    return JsonResponse({'success': True})

def friend_requests(request):
    return render(request, 'chat/friends.html')

def send_friend_request(request, user_id):
    return redirect('friend_requests')

def accept_friend_request(request, request_id):
    return redirect('friend_requests')

def decline_friend_request(request, request_id):
    return redirect('friend_requests')

def cancel_friend_request(request, request_id):
    return redirect('friend_requests')

# ===== Boutique E-commerce =====

def shop_home(request):
    try:
        categories = ProductCategory.objects.filter(is_active=True, parent=None)[:6]
        featured_products = Product.objects.filter(status='active', is_featured=True)[:8]
        new_products = Product.objects.filter(status='active').order_by('-created_at')[:8]
        context = {
            'categories': categories,
            'featured_products': featured_products,
            'new_products': new_products,
        }
        return render(request, 'shop/home.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_home: {e}")
        messages.error(request, "Erreur lors du chargement de la boutique")
        return redirect('index')

def shop_products(request):
    try:
        products = Product.objects.filter(status='active')
        categories = ProductCategory.objects.filter(is_active=True)
        category_slug = request.GET.get('category')
        if category_slug:
            products = products.filter(category__slug=category_slug)
        min_price = request.GET.get('min_price')
        if min_price:
            products = products.filter(price__gte=min_price)
        max_price = request.GET.get('max_price')
        if max_price:
            products = products.filter(price__lte=max_price)
        sort = request.GET.get('sort', '-created_at')
        if sort in ['name', '-name', 'price', '-price', '-created_at', 'created_at']:
            products = products.order_by(sort)
        paginator = Paginator(products, 12)
        page_number = request.GET.get('page')
        products = paginator.get_page(page_number)
        context = {
            'products': products,
            'categories': categories,
            'current_sort': sort,
        }
        return render(request, 'shop/products.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_products: {e}")
        messages.error(request, "Erreur lors du chargement des produits")
        return redirect('shop_home')

def shop_product_detail(request, slug):
    try:
        product = get_object_or_404(Product, slug=slug, status='active')
        # Récupérer toutes les images du produit pour le carrousel
        product_images = product.images.all().order_by('order')
        # Si pas d'images, utiliser l'image principale
        if not product_images.exists() and product.featured_image:
            product_images = [product.featured_image]
        related_products = Product.objects.filter(category=product.category, status='active').exclude(id=product.id)[:4]
        context = {
            'product': product,
            'product_images': product_images,
            'related_products': related_products,
        }
        return render(request, 'shop/product_detail.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_product_detail: {e}")
        messages.error(request, "Produit non trouvé")
        return redirect('shop_products')

def shop_category(request, slug):
    try:
        category = get_object_or_404(ProductCategory, slug=slug, is_active=True)
        products = Product.objects.filter(category=category, status='active')
        min_price = request.GET.get('min_price')
        if min_price:
            products = products.filter(price__gte=min_price)
        max_price = request.GET.get('max_price')
        if max_price:
            products = products.filter(price__lte=max_price)
        sort = request.GET.get('sort', '-created_at')
        if sort in ['name', '-name', 'price', '-price', '-created_at']:
            products = products.order_by(sort)
        paginator = Paginator(products, 12)
        page_number = request.GET.get('page')
        products = paginator.get_page(page_number)
        context = {
            'category': category,
            'products': products,
            'current_sort': sort,
            'price_min': min_price,
            'price_max': max_price,
        }
        return render(request, 'shop/category.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_category: {e}")
        messages.error(request, "Catégorie non trouvée")
        return redirect('shop_products')

# ===== Panier =====

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart

@require_POST
def add_to_cart(request):
    try:
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        variant_id = request.POST.get('variant_id')
        if not product_id:
            return JsonResponse({'success': False, 'message': 'Produit non spécifié'})
        product = get_object_or_404(Product, id=product_id, status='active')
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
            price = variant.get_final_price()
        else:
            price = product.price
        cart = get_or_create_cart(request)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity, 'price': price}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return JsonResponse({'success': True, 'message': 'Produit ajouté au panier', 'cart_count': cart.get_total_items()})
    except Exception as e:
        logger.error(f"Erreur add_to_cart: {e}")
        return JsonResponse({'success': False, 'message': "Erreur lors de l'ajout au panier"})

def cart_view(request):
    try:
        cart = get_or_create_cart(request)
        return render(request, 'shop/cart.html', {'cart': cart})
    except Exception as e:
        logger.error(f"Erreur cart_view: {e}")
        messages.error(request, "Erreur lors du chargement du panier")
        return redirect('shop_home')

@require_POST
def update_cart_item(request):
    try:
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Erreur update_cart_item: {e}")
        return JsonResponse({'success': False, 'message': 'Erreur lors de la mise à jour'})

@require_POST
def remove_from_cart(request):
    try:
        item_id = request.POST.get('item_id')
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Erreur remove_from_cart: {e}")
        return JsonResponse({'success': False, 'message': 'Erreur lors de la suppression'})

# ===== Checkout et Paiement Boutique (CinetPay) =====

def checkout(request):
    try:
        cart = get_or_create_cart(request)
        if cart.is_empty:
            messages.warning(request, 'Votre panier est vide')
            return redirect('cart_view')
        if request.method == 'POST':
            try:
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    customer_email=request.POST.get('email'),
                    customer_phone=request.POST.get('phone'),
                    customer_first_name=request.POST.get('first_name'),
                    customer_last_name=request.POST.get('last_name'),
                    shipping_address_line1=request.POST.get('address_line1'),
                    shipping_address_line2=request.POST.get('address_line2', ''),
                    shipping_city=request.POST.get('city'),
                    shipping_state=request.POST.get('state'),
                    shipping_postal_code=request.POST.get('postal_code'),
                    shipping_country=request.POST.get('country'),
                    subtotal=cart.get_total_price(),
                    total_amount=cart.get_total_price(),
                )
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        product_name=cart_item.product.name,
                        product_price=cart_item.price,
                        quantity=cart_item.quantity,
                        total_price=cart_item.get_total_price()
                    )
                cart.items.all().delete()
                return redirect('shop_payment', order_id=order.id)
            except Exception as e:
                logger.error(f"Erreur lors de la création de commande: {e}")
                messages.error(request, 'Erreur lors de la création de la commande')
        return render(request, 'shop/checkout.html', {'cart': cart})
    except Exception as e:
        logger.error(f"Erreur checkout: {e}")
        messages.error(request, 'Erreur lors du processus de commande')
        return redirect('cart_view')

def shop_payment(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        if order.user and request.user.is_authenticated and order.user != request.user:
            messages.error(request, 'Commande non autorisée')
            return redirect('shop_home')
        if request.method == 'POST':
            customer_data = {
                'customer_name': request.POST.get('customer_name'),
                'customer_surname': request.POST.get('customer_surname'),
                'customer_email': request.POST.get('customer_email'),
                'customer_phone_number': request.POST.get('customer_phone_number'),
                'customer_address': request.POST.get('customer_address'),
                'customer_city': request.POST.get('customer_city'),
                'customer_country': request.POST.get('customer_country'),
                'customer_state': request.POST.get('customer_state'),
                'customer_zip_code': request.POST.get('customer_zip_code'),
            }
            cinetpay_api = CinetPayAPI()
            result = cinetpay_api.initiate_payment(order, customer_data)
            if result['success']:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect_url': result['payment_url']})
                return redirect(result['payment_url'])
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': result['error']})
                messages.error(request, f"Erreur de paiement: {result['error']}")
        return render(request, 'shop/payment.html', {'order': order, 'user_profile': getattr(request.user, 'profile', None) if request.user.is_authenticated else None})
    except Exception as e:
        logger.error(f"Erreur shop_payment: {e}")
        messages.error(request, 'Erreur lors du processus de paiement')
        return redirect('shop_home')

@csrf_exempt
def shop_cinetpay_notification(request):
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                notification_data = json.loads(request.body)
            else:
                notification_data = request.POST.dict()
            logger.info(f"Notification CinetPay reçue: {notification_data}")
            success = handle_cinetpay_notification(notification_data)
            if success:
                return HttpResponse('OK', status=200)
            return HttpResponse('Error', status=400)
        except Exception as e:
            logger.error(f"Erreur dans shop_cinetpay_notification: {e}")
            return HttpResponse('Error', status=500)
    return HttpResponse('Method not allowed', status=405)

def shop_payment_success(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        if hasattr(order, 'cinetpay_transaction') and order.cinetpay_transaction.status == 'completed':
            order.payment_status = 'paid'
            order.save()
        return render(request, 'shop/payment_success.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur shop_payment_success: {e}")
        messages.error(request, 'Erreur lors de la confirmation de paiement')
        return redirect('shop_home')

def shop_payment_failed(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        return render(request, 'shop/payment_failed.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur shop_payment_failed: {e}")
        messages.error(request, "Erreur lors de l'affichage de l'échec")
        return redirect('shop_home')

@login_required
def my_orders(request):
    try:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        paginator = Paginator(orders, 10)
        page_number = request.GET.get('page')
        orders = paginator.get_page(page_number)
        return render(request, 'shop/my_orders.html', {'orders': orders})
    except Exception as e:
        logger.error(f"Erreur my_orders: {e}")
        messages.error(request, 'Erreur lors du chargement des commandes')
        return redirect('shop_home')

@login_required
def order_detail(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id, user=request.user)
        return render(request, 'shop/order_detail.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur order_detail: {e}")
        messages.error(request, 'Commande non trouvée')
        return redirect('my_orders')

@login_required
def sync_shopify_products(request):
    if not request.user.is_staff:
        messages.error(request, 'Accès non autorisé')
        return redirect('index')
    try:
        count = sync_products_from_shopify()
        messages.success(request, f"{count} produits synchronisés depuis Shopify")
    except Exception as e:
        logger.error(f"Erreur sync_shopify_products: {e}")
        messages.error(request, f"Erreur lors de la synchronisation: {e}")
    return redirect('shop_home')

# ===== Paramétrage des infos de paiement vendeur (stubs) =====

@login_required
def seller_payment_setup(request):
    payment_info, _ = SellerPaymentInfo.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        payment_info.preferred_payment_method = request.POST.get('preferred_payment_method', payment_info.preferred_payment_method)
        payment_info.phone_number = request.POST.get('phone_number', payment_info.phone_number)
        payment_info.operator = request.POST.get('operator', payment_info.operator)
        payment_info.country = request.POST.get('country', payment_info.country)
        payment_info.save()
        messages.success(request, 'Informations de paiement mises à jour')
        return redirect('seller_payment_setup')
    return render(request, 'seller_payment_setup.html', {'payment_info': payment_info})

@login_required
def reset_payment_info(request):
    payment_info, _ = SellerPaymentInfo.objects.get_or_create(user=request.user)
    payment_info.delete()
    messages.success(request, 'Informations de paiement réinitialisées')
    return redirect('seller_payment_setup')

# ===== HIGHLIGHTS SYSTEM =====

def highlights_home(request):
    """Page d'accueil des Highlights avec navigation"""
    try:
        # Récupérer quelques highlights récents pour l'aperçu
        recent_highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').order_by('-created_at')[:10]
        
        # Statistiques pour l'utilisateur connecté
        user_stats = {}
        if request.user.is_authenticated:
            user_stats = {
                'highlights_count': Highlight.objects.filter(author=request.user, is_active=True).count(),
                'subscribers_count': request.user.subscribers.count(),
                'subscriptions_count': request.user.subscriptions.count(),
            }
        
        context = {
            'recent_highlights': recent_highlights,
            'user_stats': user_stats,
        }
        return render(request, 'highlights/home.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_home: {e}")
        messages.error(request, "Erreur lors du chargement des Highlights")
        return redirect('index')

def highlights_for_you(request):
    """Feed personnalisé des Highlights"""
    try:
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').prefetch_related(
            'likes', 'comments', 'views'
        ).order_by('-created_at')
        
        # Si l'utilisateur est connecté, prioriser les highlights des abonnements
        if request.user.is_authenticated:
            subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
            highlights = highlights.annotate(
                is_from_subscription=Exists(
                    UserSubscription.objects.filter(
                        subscriber=request.user,
                        subscribed_to=OuterRef('author')
                    )
                )
            ).order_by('-is_from_subscription', '-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        context = {
            'highlights': highlights,
            'page_title': 'Pour Toi',
        }
        return render(request, 'highlights/feed.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_for_you: {e}")
        messages.error(request, "Erreur lors du chargement du feed")
        return redirect('highlights_home')

@login_required
def highlights_friends(request):
    """Highlights des amis/abonnements uniquement"""
    try:
        subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
        
        highlights = Highlight.objects.filter(
            author__in=subscribed_users,
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').prefetch_related(
            'likes', 'comments', 'views'
        ).order_by('-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        context = {
            'highlights': highlights,
            'page_title': 'Amis',
        }
        return render(request, 'highlights/feed.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_friends: {e}")
        messages.error(request, "Erreur lors du chargement des highlights d'amis")
        return redirect('highlights_home')

def highlights_search(request):
    """Recherche de Highlights par hashtags ou utilisateurs"""
    try:
        query = request.GET.get('q', '').strip()
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile')
        
        if query:
            if query.startswith('#'):
                # Recherche par hashtag
                hashtag = query[1:].lower()
                highlights = highlights.filter(hashtags__icontains=hashtag)
            else:
                # Recherche par utilisateur ou caption
                highlights = highlights.filter(
                    Q(author__username__icontains=query) |
                    Q(caption__icontains=query)
                )
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        # Hashtags populaires
        popular_hashtags = []
        try:
            all_hashtags = []
            for h in Highlight.objects.filter(is_active=True, expires_at__gt=timezone.now()).values_list('hashtags', flat=True):
                if h:
                    all_hashtags.extend(h)
            
            from collections import Counter
            hashtag_counts = Counter(all_hashtags)
            popular_hashtags = [tag for tag, count in hashtag_counts.most_common(10)]
        except Exception:
            pass
        
        context = {
            'highlights': highlights,
            'query': query,
            'popular_hashtags': popular_hashtags,
            'page_title': 'Recherche',
        }
        return render(request, 'highlights/search.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_search: {e}")
        messages.error(request, "Erreur lors de la recherche")
        return redirect('highlights_home')

def highlights_hashtag(request, hashtag):
    """Highlights pour un hashtag spécifique"""
    try:
        highlights = Highlight.objects.filter(
            hashtags__icontains=hashtag.lower(),
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').order_by('-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        context = {
            'highlights': highlights,
            'hashtag': hashtag,
            'page_title': f'#{hashtag}',
        }
        return render(request, 'highlights/hashtag.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_hashtag: {e}")
        messages.error(request, "Erreur lors du chargement du hashtag")
        return redirect('highlights_search')

@login_required
def create_highlight(request):
    """Créer un nouveau Highlight"""
    try:
        if request.method == 'POST':
            video = request.FILES.get('video')
            caption = request.POST.get('caption', '').strip()
            
            if not video:
                messages.error(request, 'Veuillez sélectionner une vidéo')
                return render(request, 'highlights/create.html')
            
            # Extraire les hashtags de la caption
            hashtags = re.findall(r'#(\w+)', caption.lower())
            
            # Créer le highlight
            highlight = Highlight.objects.create(
                author=request.user,
                video=video,
                caption=caption,
                hashtags=hashtags
            )
            
            messages.success(request, 'Highlight créé avec succès!')
            return redirect('highlight_detail', highlight_id=highlight.id)
        
        return render(request, 'highlights/create.html')
    except Exception as e:
        logger.error(f"Erreur create_highlight: {e}")
        messages.error(request, "Erreur lors de la création du Highlight")
        return redirect('highlights_home')

def highlight_detail(request, highlight_id):
    """Détail d'un Highlight avec commentaires"""
    try:
        highlight = get_object_or_404(
            Highlight.objects.select_related('author', 'author__profile'),
            id=highlight_id,
            is_active=True
        )
        
        # Vérifier si le highlight n'est pas expiré
        if highlight.is_expired:
            messages.warning(request, "Ce Highlight a expiré")
            return redirect('highlights_home')
        
        # Enregistrer la vue
        if request.user.is_authenticated:
            HighlightView.objects.get_or_create(
                highlight=highlight,
                user=request.user,
                defaults={'ip_address': request.META.get('REMOTE_ADDR')}
            )
        
        # Récupérer les commentaires
        comments = highlight.comments.select_related('user', 'user__profile').order_by('-created_at')
        
        # Vérifier si l'utilisateur a liké
        user_liked = False
        if request.user.is_authenticated:
            user_liked = highlight.likes.filter(user=request.user).exists()
        
        context = {
            'highlight': highlight,
            'comments': comments,
            'user_liked': user_liked,
        }
        return render(request, 'highlights/detail.html', context)
    except Exception as e:
        logger.error(f"Erreur highlight_detail: {e}")
        messages.error(request, "Highlight non trouvé")
        return redirect('highlights_home')

@login_required
def delete_highlight(request, highlight_id):
    """Supprimer un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, author=request.user)
        
        if request.method == 'POST':
            highlight.delete()
            messages.success(request, 'Highlight supprimé avec succès')
            return redirect('highlights_home')
        
        return render(request, 'highlights/confirm_delete.html', {'highlight': highlight})
    except Exception as e:
        logger.error(f"Erreur delete_highlight: {e}")
        messages.error(request, "Erreur lors de la suppression")
        return redirect('highlights_home')

@login_required
@require_POST
def toggle_highlight_like(request, highlight_id):
    """Liker/Unliker un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        
        like, created = HighlightLike.objects.get_or_create(
            highlight=highlight,
            user=request.user
        )
        
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'liked': liked,
                'likes_count': highlight.likes_count
            })
        
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur toggle_highlight_like: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def add_highlight_comment(request, highlight_id):
    """Ajouter un commentaire à un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Commentaire vide'})
        
        comment = HighlightComment.objects.create(
            highlight=highlight,
            user=request.user,
            content=content
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': str(comment.id),
                    'content': comment.content,
                    'user': comment.user.username,
                    'created_at': comment.created_at.strftime('%H:%M'),
                    'user_avatar': comment.user.profile.profileimg.url if hasattr(comment.user, 'profile') and comment.user.profile.profileimg else None
                },
                'comments_count': highlight.comments_count
            })
        
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur add_highlight_comment: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def share_highlight(request, highlight_id):
    """Partager un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        shared_to_id = request.POST.get('shared_to')
        
        shared_to = None
        if shared_to_id:
            shared_to = get_object_or_404(User, id=shared_to_id)
        
        share = HighlightShare.objects.create(
            highlight=highlight,
            user=request.user,
            shared_to=shared_to
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Highlight partagé'})
        
        messages.success(request, 'Highlight partagé avec succès')
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur share_highlight: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def record_highlight_view(request, highlight_id):
    """Enregistrer une vue sur un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        
        if request.user.is_authenticated:
            view, created = HighlightView.objects.get_or_create(
                highlight=highlight,
                user=request.user,
                defaults={'ip_address': request.META.get('REMOTE_ADDR')}
            )
        else:
            # Pour les utilisateurs anonymes, utiliser l'IP
            ip_address = request.META.get('REMOTE_ADDR')
            if ip_address:
                view, created = HighlightView.objects.get_or_create(
                    highlight=highlight,
                    ip_address=ip_address,
                    user=None
                )
        
        return JsonResponse({'success': True, 'views_count': highlight.views.count()})
    except Exception as e:
        logger.error(f"Erreur record_highlight_view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def toggle_subscription(request, user_id):
    """S'abonner/Se désabonner d'un utilisateur"""
    try:
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user == request.user:
            return JsonResponse({'success': False, 'error': 'Impossible de s\'abonner à soi-même'})
        
        subscription, created = UserSubscription.objects.get_or_create(
            subscriber=request.user,
            subscribed_to=target_user
        )
        
        if not created:
            subscription.delete()
            subscribed = False
            action = 'désabonné'
        else:
            subscribed = True
            action = 'abonné'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'subscribed': subscribed,
                'action': action,
                'subscribers_count': target_user.subscribers.count()
            })
        
        messages.success(request, f'Vous êtes maintenant {action} à {target_user.username}')
        return redirect('profile', username=target_user.username)
    except Exception as e:
        logger.error(f"Erreur toggle_subscription: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def my_subscriptions(request):
    """Liste des abonnements de l'utilisateur"""
    try:
        subscriptions = UserSubscription.objects.filter(
            subscriber=request.user
        ).select_related('subscribed_to', 'subscribed_to__profile').order_by('-created_at')
        
        context = {
            'subscriptions': subscriptions,
        }
        return render(request, 'highlights/subscriptions.html', context)
    except Exception as e:
        logger.error(f"Erreur my_subscriptions: {e}")
        messages.error(request, "Erreur lors du chargement des abonnements")
        return redirect('highlights_home')

@login_required
def my_subscribers(request):
    """Liste des abonnés de l'utilisateur"""
    try:
        subscribers = UserSubscription.objects.filter(
            subscribed_to=request.user
        ).select_related('subscriber', 'subscriber__profile').order_by('-created_at')
        
        context = {
            'subscribers': subscribers,
        }
        return render(request, 'highlights/subscribers.html', context)
    except Exception as e:
        logger.error(f"Erreur my_subscribers: {e}")
        messages.error(request, "Erreur lors du chargement des abonnés")
        return redirect('highlights_home')

# ===== API HIGHLIGHTS (AJAX) =====

def highlights_feed_api(request):
    """API pour le feed des Highlights (AJAX)"""
    try:
        page = int(request.GET.get('page', 1))
        feed_type = request.GET.get('type', 'for_you')
        
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile')
        
        if feed_type == 'friends' and request.user.is_authenticated:
            subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
            highlights = highlights.filter(author__in=subscribed_users)
        
        highlights = highlights.order_by('-created_at')
        
        paginator = Paginator(highlights, 10)
        highlights_page = paginator.get_page(page)
        
        highlights_data = []
        for highlight in highlights_page:
            user_liked = False
            if request.user.is_authenticated:
                user_liked = highlight.likes.filter(user=request.user).exists()
            
            highlights_data.append({
                'id': str(highlight.id),
                'video_url': highlight.video.url,
                'caption': highlight.caption,
                'hashtags': highlight.hashtags,
                'author': {
                    'username': highlight.author.username,
                    'avatar': highlight.author.profile.profileimg.url if hasattr(highlight.author, 'profile') and highlight.author.profile.profileimg else None
                },
                'likes_count': highlight.likes_count,
                'comments_count': highlight.comments_count,
                'views_count': highlight.views.count(),
                'user_liked': user_liked,
                'created_at': highlight.created_at.strftime('%H:%M'),
                'time_remaining': str(highlight.time_remaining) if highlight.time_remaining else None
            })
        
        return JsonResponse({
            'success': True,
            'highlights': highlights_data,
            'has_next': highlights_page.has_next(),
            'next_page': highlights_page.next_page_number() if highlights_page.has_next() else None
        })
    except Exception as e:
        logger.error(f"Erreur highlights_feed_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

def highlight_comments_api(request, highlight_id):
    """API pour les commentaires d'un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        comments = highlight.comments.select_related('user', 'user__profile').order_by('-created_at')
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'id': str(comment.id),
                'content': comment.content,
                'user': {
                    'username': comment.user.username,
                    'avatar': comment.user.profile.profileimg.url if hasattr(comment.user, 'profile') and comment.user.profile.profileimg else None
                },
                'created_at': comment.created_at.strftime('%H:%M')
            })
        
        return JsonResponse({
            'success': True,
            'comments': comments_data
        })
    except Exception as e:
        logger.error(f"Erreur highlight_comments_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
