# Azure App Service Deployment
# Simpler but may have WebSocket limitations

$resourceGroup = "epic-retro-rg"
$location = "North Europe"  # Stockholm region - optimal for Sweden
$appName = "code-typing-championship"  # Must be globally unique
$planName = "epic-retro-plan"

# Create resource group
az group create --name $resourceGroup --location $location

# Create App Service plan
az appservice plan create --name $planName --resource-group $resourceGroup --sku B1 --is-linux

# Create web app
az webapp create --resource-group $resourceGroup --plan $planName --name $appName --runtime "PYTHON|3.11"

# Configure startup command
az webapp config set --resource-group $resourceGroup --name $appName --startup-file "python server.py"

# Deploy code (requires git repo)
# az webapp deployment source config --name $appName --resource-group $resourceGroup --repo-url https://github.com/yourusername/epic_retro --branch main --manual-integration

Write-Host "Your game will be available at: https://$appName.azurewebsites.net"