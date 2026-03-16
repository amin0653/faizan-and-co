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
    """Website se title, image, description aur price extract karta hai"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Title
        title = soup.find('meta', property='og:title')
        title = title['content'] if title else soup.title.string
        
        # Image
        image = soup.find('meta', property='og:image')
        image_url = image['content'] if image else None
        
        # Description
        desc = soup.find('meta', property='og:description')
        description = desc['content'] if desc else "No description available."
        
        # Price (multiple patterns)
        price = None
        price_patterns = [
            r'Rs\.\s*([\d,]+\.?\d*)',
            r'PKR\s*([\d,]+\.?\d*)',
            r'\$\s*([\d,]+\.?\d*)',
            r'£\s*([\d,]+\.?\d*)',
            r'€\s*([\d,]+\.?\d*)',
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
    """Home page - sab products dikhayega"""
    query = request.GET.get('q', '')
    if query:
        products = Product.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).order_by('-created_at')
    else:
        products = Product.objects.all().order_by('-created_at')
    
    return render(request, 'store/index.html', {'products': products, 'query': query})


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def add_product(request):
    """Product add - Auto fetch ya Manual entry"""
    if request.method == 'POST':
        link = request.POST.get('link', '').strip()
        email = request.POST.get('email', '').strip()
        title = request.POST.get('title', '').strip()
        image_url = request.POST.get('image_url', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '0.00')
        image_upload = request.FILES.get('image_upload')
        
        # Auto-fetch sirf tab jab link ho aur fields khali hon
        if link and (not title or not description):
            auto_title, auto_image, auto_desc, auto_price = get_meta_info(link)
            if not title:
                title = auto_title
            if not image_url and not image_upload:
                image_url = auto_image
            if not description:
                description = auto_desc
            if not price or price == '0.00':
                price = auto_price if auto_price else '0.00'
        
        # Validation - Sirf Title aur Description zaroori
        if not title or not description:
            messages.error(request, 'Title aur Description zaroori hain!')
            return render(request, 'store/add_product.html')
        
        # Product create
        product = Product.objects.create(
            title=title,
            image_url=image_url,
            description=description,
            price=price,
            original_link=link if link else None,
            seller_email=email if email else None
        )
        
        if image_upload:
            product.image_upload = image_upload
            product.save()
        
        messages.success(request, 'Product successfully added!')
        return redirect('index')
        
    return render(request, 'store/add_product.html')


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def edit_product(request, product_id):
    """Product edit"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.title = request.POST.get('title', '').strip()
        product.image_url = request.POST.get('image_url', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.price = request.POST.get('price', '0.00')
        link = request.POST.get('link', '').strip()
        product.original_link = link if link else None
        product.seller_email = request.POST.get('email', '').strip()
        
        image_upload = request.FILES.get('image_upload')
        if image_upload:
            product.image_upload = image_upload
        
        product.save()
        messages.success(request, 'Product updated successfully!')
        return redirect('index')
    
    return render(request, 'store/edit_product.html', {'product': product})


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def delete_product(request, product_id):
    """Product delete"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully!')
        return redirect('index')
    
    return render(request, 'store/delete_confirm.html', {'product': product})


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def change_password(request):
    """Password change"""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        user = request.user
        
        if not user.check_password(old_password):
            messages.error(request, 'Current password is incorrect!')
            return render(request, 'store/change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match!')
            return render(request, 'store/change_password.html')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters!')
            return render(request, 'store/change_password.html')
        
        user.set_password(new_password)
        user.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        messages.success(request, 'Password changed successfully!')
        return redirect('index')
    
    return render(request, 'store/change_password.html')


def contact_view(request):
    """Contact form"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        ContactMessage.objects.create(
            name=name, email=email, subject=subject, message=message
        )
        
        return render(request, 'store/contact.html', {
            'success': 'Thank you! Your message has been sent.'
        })
    
    return render(request, 'store/contact.html')


@csrf_exempt
@login_required(login_url='/login/')
def fetch_details(request):
    """AJAX - Auto fetch from URL"""
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
            return JsonResponse({'success': False, 'error': 'No URL'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def user_login(request):
    """Admin login"""
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
    """Logout"""
    logout(request)
    return redirect('index')