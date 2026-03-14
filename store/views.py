from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.contrib.auth.backends import ModelBackend
from .models import Product, ContactMessage
import requests
from bs4 import BeautifulSoup
import re
import json

def get_meta_info(url):
    """
    Website se title, image, description aur price extract karta hai
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Title extract karna
        title = soup.find('meta', property='og:title')
        title = title['content'] if title else soup.title.string
        
        # Image extract karna
        image = soup.find('meta', property='og:image')
        image_url = image['content'] if image else None
        
        # Description extract karna
        desc = soup.find('meta', property='og:description')
        description = desc['content'] if desc else "No description available."
        
        # Price extract karna (multiple currencies support)
        price = None
        price_patterns = [
            r'Rs\.\s*([\d,]+\.?\d*)',
            r'PKR\s*([\d,]+\.?\d*)',
            r'\$\s*([\d,]+\.?\d*)',
            r'£\s*([\d,]+\.?\d*)',
            r'€\s*([\d,]+\.?\d*)',
            r'price["\']?\s*[:=]\s*["\']?([\d,]+\.?\d*)',
        ]
        
        for pattern in price_patterns:
            price_match = re.search(pattern, response.text, re.IGNORECASE)
            if price_match:
                price = price_match.group(1).replace(',', '')
                break
        
        return title, image_url, description, price
    except Exception as e:
        return "Unknown Title", None, "Could not fetch details.", None


def index(request):
    """
    Home page - sab products dikhayega with search
    """
    query = request.GET.get('q', '')
    if query:
        products = Product.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        ).order_by('-created_at')
    else:
        products = Product.objects.all().order_by('-created_at')
    
    return render(request, 'store/index.html', {
        'products': products,
        'query': query
    })


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def add_product(request):
    """
    Naya product add karne ka view - Admin only
    """
    if request.method == 'POST':
        link = request.POST.get('link')
        email = request.POST.get('email')
        title = request.POST.get('title')
        image_url = request.POST.get('image_url')
        description = request.POST.get('description')
        price = request.POST.get('price', '0.00')
        image_upload = request.FILES.get('image_upload')
        
        # Auto-fetch agar fields khali hain
        if not title or not description:
            auto_title, auto_image, auto_desc, auto_price = get_meta_info(link)
            if not title:
                title = auto_title
            if not image_url and not image_upload:
                image_url = auto_image
            if not description:
                description = auto_desc
            if not price or price == '0.00':
                price = auto_price if auto_price else '0.00'
        
        # Product create karna
        product = Product.objects.create(
            title=title,
            image_url=image_url,
            description=description,
            price=price,
            original_link=link,
            seller_email=email
        )
        
        # Uploaded image save karna (agar hai)
        if image_upload:
            product.image_upload = image_upload
            product.save()
        
        return redirect('index')
        
    return render(request, 'store/add_product.html')


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def edit_product(request, product_id):
    """
    Product edit karne ka view - Admin only
    """
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.title = request.POST.get('title')
        product.image_url = request.POST.get('image_url')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price', '0.00')
        product.original_link = request.POST.get('link')
        product.seller_email = request.POST.get('email')
        
        # Image upload handle karna
        image_upload = request.FILES.get('image_upload')
        if image_upload:
            product.image_upload = image_upload
        
        product.save()
        return redirect('index')
    
    return render(request, 'store/edit_product.html', {'product': product})


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def delete_product(request, product_id):
    """
    Product delete karne ka view - Admin only with confirmation
    """
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.delete()
        return redirect('index')
    
    return render(request, 'store/delete_confirm.html', {'product': product})


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def change_password(request):
    """
    Admin apna password change kar sake - Secure implementation
    """
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        user = request.user
        
        # 1. Old password check karna
        if not user.check_password(old_password):
            messages.error(request, 'Current password is incorrect!')
            return render(request, 'store/change_password.html')
        
        # 2. New passwords match check karna
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match!')
            return render(request, 'store/change_password.html')
        
        # 3. Password length check (min 8 characters)
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long!')
            return render(request, 'store/change_password.html')
        
        # 4. Password update karna
        user.set_password(new_password)
        user.save()
        
        # 5. ✅ IMPORTANT: Multiple backends ke liye backend specify karna
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        messages.success(request, 'Password changed successfully!')
        return redirect('index')
    
    return render(request, 'store/change_password.html')


def contact_view(request):
    """
    Contact form - Users message bhej saken
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Database mein save karna
        ContactMessage.objects.create(
            name=name,
            email=email,
            subject=subject,
            message=message
        )
        
        # Optional: Admin ko email bhejna (agar configured hai)
        try:
            from django.core.mail import send_mail
            send_mail(
                f'New Contact: {subject}',
                f'From: {name}\nEmail: {email}\n\n{message}',
                email,
                ['admin@faizanandco.com'],
                fail_silently=True,
            )
        except:
            pass  # Email config na ho to ignore
        
        return render(request, 'store/contact.html', {
            'success': 'Thank you! Your message has been sent successfully.'
        })
    
    return render(request, 'store/contact.html')


@csrf_exempt
@login_required(login_url='/login/')
def fetch_details(request):
    """
    AJAX endpoint - Auto-fetch product details from URL
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            url = data.get('url')
            
            if url:
                title, image_url, description, price = get_meta_info(url)
                return JsonResponse({
                    'success': True,
                    'title': title,
                    'image_url': image_url,
                    'description': description,
                    'price': price if price else '0.00'
                })
            return JsonResponse({'success': False, 'error': 'No URL provided'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def user_login(request):
    """
    Admin login view with security
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('add_product')
        else:
            return render(request, 'store/login.html', {
                'error': 'Sirf Admin login kar sakta hai!'
            })
            
    return render(request, 'store/login.html')


def user_logout(request):
    """
    Admin logout view
    """
    logout(request)
    return redirect('index')