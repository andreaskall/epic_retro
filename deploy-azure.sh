#!/bin/bash
# Azure Container Instances Deployment Script (Linux/Mac version)
# Run this in Azure Cloud Shell or with Azure CLI installed

# Configuration - CHANGE THESE VALUES
RESOURCE_GROUP="epic-retro-rg"
LOCATION="North Europe"  # Stockholm region - closest to Sweden
CONTAINER_NAME="code-typing-championship"
IMAGE_NAME="code-typing-game"
REGISTRY_NAME="epicretroregistry"  # Must be globally unique

# Create resource group
az group create --name $RESOURCE_GROUP --location "$LOCATION"

# Create Azure Container Registry
az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY_NAME --sku Basic

# Build and push image to registry
az acr build --registry $REGISTRY_NAME --image $IMAGE_NAME .

# Deploy to Container Instances
az container create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_NAME \
  --image "$REGISTRY_NAME.azurecr.io/$IMAGE_NAME:latest" \
  --dns-name-label $CONTAINER_NAME \
  --ports 5000 \
  --environment-variables FLASK_ENV=production \
  --cpu 1 --memory 1 \
  --registry-login-server "$REGISTRY_NAME.azurecr.io" \
  --registry-username $REGISTRY_NAME \
  --registry-password $(az acr credential show --name $REGISTRY_NAME --query "passwords[0].value" -o tsv)

# Get public URL
PUBLIC_IP=$(az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_NAME --query ipAddress.fqdn -o tsv)
echo "Your game is available at: http://$PUBLIC_IP:5000"
echo "Master interface at: http://$PUBLIC_IP:5000/master"