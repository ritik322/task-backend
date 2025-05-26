from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Document

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirm Password")

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'password2', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password_confirmation": "Password fields didn't match."})
        # Remove password2 as it's not part of the User model
        attrs.pop('password2')
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'], # create_user handles hashing
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

class DocumentSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    # To provide the full URL to the uploaded file in the API response
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        # 'file' is for upload, 'file_url' is for read
        fields = ('id', 'user', 'title', 'file', 'file_url', 'uploaded_at', 'extracted_text')
        # 'file' field should be writable for uploads, but its URL is read-only
        read_only_fields = ('user', 'uploaded_at', 'extracted_text', 'file_url')
        extra_kwargs = {
            'file': {'write_only': True} # Use file for upload, file_url for retrieval
        }

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None