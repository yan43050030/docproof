@echo off
chcp 65001 >nul
echo ========================================
echo   DocProof Windows 便携版构建脚本
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 创建虚拟环境...
python -m venv build_env
call build_env\Scripts\activate.bat

echo [2/4] 安装依赖...
pip install --upgrade pip
pip install PySide6 python-docx kenlm pycorrector pyinstaller

echo [3/4] 构建便携版...
pyinstaller --noconfirm ^
    --name="DocProof" ^
    --windowed ^
    --onedir ^
    --icon="docproof/resources/icon.ico" ^
    --add-data="third_party/pycorrector/pycorrector;pycorrector" ^
    --add-data="models;models" ^
    --hidden-import="pycorrector" ^
    --hidden-import="pycorrector.corrector" ^
    --hidden-import="pycorrector.detector" ^
    --hidden-import="pycorrector.proper_corrector" ^
    --hidden-import="pycorrector.utils" ^
    --hidden-import="pycorrector.utils.text_utils" ^
    --hidden-import="pycorrector.utils.tokenizer" ^
    --hidden-import="pycorrector.utils.get_file" ^
    --hidden-import="kenlm" ^
    --hidden-import="pypinyin" ^
    --hidden-import="jieba" ^
    --exclude-module="torch" ^
    --exclude-module="transformers" ^
    --exclude-module="paddle" ^
    docproof\__main__.py

if %errorlevel% neq 0 (
    echo [错误] 构建失败！
    pause
    exit /b 1
)

echo [4/4] 整理便携版目录...
if exist "dist\DocProof-portable" rmdir /s /q "dist\DocProof-portable"
rename "dist\DocProof" "DocProof-portable"

REM Create empty models dir if not copied
if not exist "dist\DocProof-portable\models" mkdir "dist\DocProof-portable\models"

REM Copy launch instructions
(
echo DocProof 便携版使用说明
echo ========================
echo.
echo 1. 将语言模型文件(.klm)放入 models 文件夹
echo 2. 双击 DocProof.exe 启动
echo 3. 首次启动会提示下载模型，选择"已有模型"即可
echo.
echo 模型下载地址:
echo   标准模型(141MB): https://github.com/shibing624/pycorrector/releases/download/1.0.0/people2014corpus_chars.klm
echo   大型模型(2.95GB): https://deepspeech.bj.bcebos.com/zh_lm/zh_giga.no_cna_cmn.prune01244.klm
) > "dist\DocProof-portable\使用说明.txt"

echo.
echo ========================================
echo   构建完成！
echo   便携版位置: dist\DocProof-portable\
echo ========================================
echo.
echo 目录内容:
dir "dist\DocProof-portable" /b
echo.
echo 发布时将此目录打包为 zip 即可:
echo   选中 DocProof-portable 文件夹 → 右键 → 压缩
echo.
pause
