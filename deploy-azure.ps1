# Azure Container Instances Deployment Script
# Run this in Azure Cloud Shell or with Azure CLI installed

# Configuration - CHANGE THESE VALUES
$resourceGroup = "epic-retro-rg"
$location = "North Europe"  # Stockholm region - closest to Sweden
$containerName = "code-typing-championship"
$imageName = "code-typing-game"
$registryName = "epicretroregistry"  # Must be globally unique

# Create resource group
az group create --name $resourceGroup --location $location

# Create Azure Container Registry
az acr create --resource-group $resourceGroup --name $registryName --sku Basic

# Build and push image to registry
az acr build --registry $registryName --image $imageName .

# Deploy to Container Instances
az container create `
  --resource-group $resourceGroup `
  --name $containerName `
  --image "$registryName.azurecr.io/$imageName:latest" `
  --dns-name-label $containerName `
  --ports 5000 `
  --environment-variables FLASK_ENV=production `
  --cpu 1 --memory 1 `
  --registry-login-server "$registryName.azurecr.io" `
  --registry-username $registryName `
  --registry-password $(az acr credential show --name $registryName --query "passwords[0].value" -o tsv)

# Get public URL
$publicIP = az container show --resource-group $resourceGroup --name $containerName --query ipAddress.fqdn -o tsv
Write-Host "Your game is available at: http://$publicIP:5000"
Write-Host "Master interface at: http://$publicIP:5000/master"