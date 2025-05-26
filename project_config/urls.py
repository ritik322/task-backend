from django.contrib import admin
from django.urls import path, include # Ensure 'include' is imported
from django.conf import settings # For serving media files in development
from django.conf.urls.static import static # For serving media files in development

from rest_framework_simplejwt.views import ( # Import JWT views
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('admin/', admin.site.urls), # Django admin site

    # JWT Token Endpoints (for login and refreshing tokens)
    # The client will POST username/password to /api/login/ to get tokens
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # The client will POST a valid refresh token to /api/login/refresh/ to get a new access token
    path('api/login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Include URLs from your 'api' app
    # All URLs defined in 'api.urls' will be prefixed with 'api/'
    # So, your registration URL will be '/api/register/', documents will be '/api/documents/', etc.
    path('api/', include('api.urls')),
]

# Add this block at the end of the file to serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)