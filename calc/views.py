from django.shortcuts import render              # Import render to return an HTML template

# Home view - renders the home.html template
def home(request):
    return render(request, 'calc/home.html')          # Pass the request to home.html and render it
# calc/views.py
from django.contrib.auth.forms import UserCreationForm  # Import the default user registration form
from django.contrib.auth import login                    # Import login method to log in a user right after registration
from django.shortcuts import render, redirect

# Register view
def register(request):
    if request.method == 'POST':  # When the form is submitted
        form = UserCreationForm(request.POST)  # Bind data to the form
        if form.is_valid():  # Check if the form data is valid
            user = form.save()  # Save the user to the database
            login(request, user)  # Log the user in automatically
            return redirect('dashboard')  # Redirect to the dashboard page after successful registration
    else:
        form = UserCreationForm()  # Create a blank form for GET request
    return render(request, 'calc/register.html', {'form': form})  # Render the register form in the template
# calc/views.py
from django.contrib.auth.decorators import login_required  # Import the login_required decorator

# Dashboard view - protected by login_required to ensure only authenticated users can access it
@login_required
def dashboard(request):
    return render(request, 'dashboard.html')  # Render the dashboard template

# calc/views.py
def base(request):
    return render(request, 'calc/base.html')
from django.shortcuts import render

def index(request):
    return render(request, 'calc/home.html')
