Authentication Setup
This document explains the authentication setup for the Inventory Management API and how to test it.

Overview
The API uses JSON Web Token (JWT) authentication provided by the djangorestframework-simplejwt library. Authentication is required to access all protected endpoints.

A.  Install Django REST Framework
    pip install djangorestframework djangorestframework-simplejwt
B. Update Django Settings
    add DRF & DRF-simplejwt to installed apps

C. Add Token Endpoints

D. Protect API Views with Permissions

E. Create Test Users
    python manage.py createsuperuser

F. Test the Endpoints


 Endpoints
1. Obtain Token

    URL: /api/token/
    Method: POST
    Request Body:
    json

    {
    "username": "your_username",
    "password": "your_password"
    }
    Response:
    json

    {
    "refresh": "refresh-token",
    "access": "access-token"
    }
2. Refresh Token

    URL: /api/token/refresh/
    Method: POST
    Request Body:
    json

    {
    "refresh": "refresh-token"
    }
    Response:

    {
    "access": "new-access-token"
    }
3. Protected Endpoints

Include the Authorization header in requests:


Authorization: Bearer <access-token>