import json
import os
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class EConfig:
    """
    Configuration manager for external configuration files.
    Implements singleton pattern to ensure single instance and efficient loading.
    """
    
    _instance: Optional['EConfig'] = None
    _config_data: Optional[Dict[str, Any]] = None
    _config_file_path: str = "eConfig.json"
    
    def __new__(cls) -> 'EConfig':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(EConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the configuration manager."""
        if self._config_data is None:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            if not os.path.exists(self._config_file_path):
                logger.error(f"Configuration file not found: {self._config_file_path}")
                self._config_data = {}
                return
            
            with open(self._config_file_path, 'r', encoding='utf-8') as file:
                self._config_data = json.load(file)
                logger.info(f"Successfully loaded configuration from {self._config_file_path}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            self._config_data = {}
        except IOError as e:
            logger.error(f"Error reading configuration file: {e}")
            self._config_data = {}
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            self._config_data = {}
    
    def reload_config(self) -> bool:
        """
        Reload configuration from file.
        
        Returns:
            bool: True if reload was successful, False otherwise
        """
        try:
            self._config_data = None
            self._load_config()
            return self._config_data is not None
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.
        
        Returns:
            Dict[str, Any]: The complete configuration
        """
        return self._config_data or {}
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path (str): Dot-separated path to the configuration value
            default (Any): Default value if key is not found
            
        Returns:
            Any: The configuration value or default
            
        Example:
            config.get_value("stripe-plans.live.pro.product-id")
        """
        if not self._config_data:
            return default
            
        keys = key_path.split('.')
        current = self._config_data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            logger.debug(f"Configuration key not found: {key_path}")
            return default
    
    def get_stripe_product_id(self, plan: str, mode: str = "live") -> Optional[str]:
        """
        Get Stripe product ID for a specific plan and mode.
        
        Args:
            plan (str): Plan name (e.g., 'pro', 'starter')
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Optional[str]: Product ID or None if not found
        """
        key_path = f"stripe-plans.{mode}.{plan.lower()}.product-id"
        return self.get_value(key_path)
    
    def get_stripe_db_name(self, plan: str, mode: str = "live") -> Optional[str]:
        """
        Get database name for a specific Stripe plan and mode.
        
        Args:
            plan (str): Plan name (e.g., 'pro', 'starter')
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Optional[str]: Database name or None if not found
        """
        key_path = f"stripe-plans.{mode}.{plan.lower()}.db-name"
        return self.get_value(key_path)
    
    def get_all_stripe_plans(self, mode: str = "live") -> Dict[str, Dict[str, str]]:
        """
        Get all Stripe plans for a specific mode.
        
        Args:
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Dict[str, Dict[str, str]]: All plans with their configuration
        """
        key_path = f"stripe-plans.{mode}"
        return self.get_value(key_path, {})
    
    def get_product_id_by_db_name(self, db_name: str, mode: str = "live") -> Optional[str]:
        """
        Get product ID by database name (reverse lookup).
        
        Args:
            db_name (str): Database name (e.g., 'Pro', 'Starter')
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Optional[str]: Product ID or None if not found
        """
        plans = self.get_all_stripe_plans(mode)
        
        for plan_name, plan_config in plans.items():
            if plan_config.get('db-name') == db_name:
                return plan_config.get('product-id')
        
        return None
    
    def get_db_name_by_product_id(self, product_id: str, mode: str = "live") -> Optional[str]:
        """
        Get database name by product ID (reverse lookup).
        
        Args:
            product_id (str): Stripe product ID
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Optional[str]: Database name or None if not found
        """
        plans = self.get_all_stripe_plans(mode)
        
        for plan_name, plan_config in plans.items():
            if plan_config.get('product-id') == product_id:
                return plan_config.get('db-name')
        
        return None
    
    def is_valid_product_id(self, product_id: str, mode: str = "live") -> bool:
        """
        Check if a product ID is valid for the given mode.
        
        Args:
            product_id (str): Stripe product ID to validate
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            bool: True if product ID exists in configuration
        """
        return self.get_db_name_by_product_id(product_id, mode) is not None
    
    def get_supported_plans(self, mode: str = "live") -> list:
        """
        Get list of supported plan names for a mode.
        
        Args:
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            list: List of plan names
        """
        plans = self.get_all_stripe_plans(mode)
        return list(plans.keys())
    
    def set_value(self, key_path: str, value: Any) -> bool:
        """
        Set a configuration value using dot notation.
        Note: This only updates the in-memory configuration, not the file.
        
        Args:
            key_path (str): Dot-separated path to the configuration value
            value (Any): Value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self._config_data:
            self._config_data = {}
            
        keys = key_path.split('.')
        current = self._config_data
        
        try:
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            return True
            
        except Exception as e:
            logger.error(f"Error setting configuration value: {e}")
            return False
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self._config_file_path, 'w', encoding='utf-8') as file:
                json.dump(self._config_data, file, indent=4, ensure_ascii=False)
            logger.info(f"Configuration saved to {self._config_file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def validate_stripe_config(self, mode: str = "live") -> Dict[str, Any]:
        """
        Validate Stripe configuration for a specific mode.
        
        Args:
            mode (str): Environment mode ('live' or 'test')
            
        Returns:
            Dict[str, Any]: Validation results
        """
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "mode": mode,
            "plans_found": 0
        }
        
        plans = self.get_all_stripe_plans(mode)
        
        if not plans:
            validation_result["is_valid"] = False
            validation_result["errors"].append(f"No plans found for mode: {mode}")
            return validation_result
        
        validation_result["plans_found"] = len(plans)
        
        for plan_name, plan_config in plans.items():
            if not plan_config.get('product-id'):
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Missing product-id for {plan_name} in {mode} mode")
            
            if not plan_config.get('db-name'):
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Missing db-name for {plan_name} in {mode} mode")
            
            product_id = plan_config.get('product-id', '')
            if product_id and not product_id.startswith('prod_'):
                validation_result["warnings"].append(f"Product ID {product_id} for {plan_name} doesn't follow expected format")
        
        return validation_result
    
    def __str__(self) -> str:
        """String representation of the configuration."""
        return f"EConfig(loaded={self._config_data is not None}, file={self._config_file_path})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return f"EConfig(config_data={self._config_data}, file_path={self._config_file_path})"


econfig = EConfig()


def get_stripe_product_id(plan: str, mode: str = "live") -> Optional[str]:
    """Convenience function to get Stripe product ID."""
    return econfig.get_stripe_product_id(plan, mode)


def get_stripe_db_name(plan: str, mode: str = "live") -> Optional[str]:
    """Convenience function to get Stripe database name."""
    return econfig.get_stripe_db_name(plan, mode)


def get_db_name_by_product_id(product_id: str, mode: str = "live") -> Optional[str]:
    """Convenience function for reverse lookup of database name."""
    return econfig.get_db_name_by_product_id(product_id, mode)


def is_valid_product_id(product_id: str, mode: str = "live") -> bool:
    """Convenience function to validate product ID."""
    return econfig.is_valid_product_id(product_id, mode)

