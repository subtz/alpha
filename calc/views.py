from django.contrib.auth.forms import UserCreationForm  # Import the default user registration form
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

# Home view - renders the home.html template
def home(request):
    return render(request, 'calc/home.html')  # Pass the request to home.html and render it

# Register view
def register(request):
    if request.method == 'POST':  # When the form is submitted
        form = UserCreationForm(request.POST)  # Bind data to the form
        if form.is_valid():  # Check if the form data is valid
            user = form.save()  # Save the user to the database
            login(request, user)  # Log the user in automatically
            return redirect('dashboard')  # Redirect to dashboard after successful registration
    else:
        form = UserCreationForm()  # Create a blank form for GET request
    return render(request, 'calc/register.html', {'form': form})  # Render the register form in the template

# Login view
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')  # or another view like 'home'
        else:
            return render(request, 'calc/login.html', {'error': 'Invalid credentials'})
    return render(request, 'calc/login.html')

# Dashboard view - protected by login_required to ensure only authenticated users can access it
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')  # Render the dashboard template

# Base view
def base(request):
    return render(request, 'calc/base.html')

# Index view
def index(request):
    return render(request, 'calc/home.html')
