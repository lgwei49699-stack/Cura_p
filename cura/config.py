"""
统一的 API 配置文件
"""
import os

# 环境配置
ENVIRONMENT = os.environ.get("CURA_ENV", "production")  # qa, production

if ENVIRONMENT == "production" or ENVIRONMENT == "prod":
    AUTH_BASE_URL = "https://dcenter.kfb-1.com"
    API_BASE_URL = "https://print.wisebeginner3d.com"
else:
    AUTH_BASE_URL = "https://qa-datacenter.gongfudou.com"
    API_BASE_URL = "https://qa-appgw.gongfudou.com"

# 认证接口
VERIFY_URL = f"{AUTH_BASE_URL}/manager/auth/login/tfaCode"
LOGIN_URL = f"{AUTH_BASE_URL}/manager/auth/login/emailPassword"
PUBLIC_KEY_URL = f"{AUTH_BASE_URL}/manager/auth/login/publicKey"

# 业务接口
OBS_TOKEN_URL = f"{API_BASE_URL}/app/print3d/api/v1/obs/token"
CONFIG_ADD_URL = f"{API_BASE_URL}/app/print3d/manage/v1/slice-param-config/add"
DEVICE_QUERY_URL = f"{API_BASE_URL}/app/print3d/manage/v1/md/query"
DEVICE_SLICE_TYPE_URL = f"{API_BASE_URL}/app/print3d/manage/v1/slice-param-config/device-and-slice-type"
DEVICE_PRINT_CMD_URL = f"{API_BASE_URL}/app/pmc/api/v1/deviceCmd/print"

# 华为云 OBS 配置
ACCESS_KEY = "RBH44LBCU4Z4BBGJB4DK"
SECRET_KEY = "iq2A0AAeYyHk1cxoCfGi9KlxVtWzb6HrUG9LZ5hH"
OBS_SERVER = "obs.cn-east-2.myhuaweicloud.com"
OBS_BUCKET_NAME = "micro"

