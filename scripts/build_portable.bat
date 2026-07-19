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

echo [1/5] 运行测试...
python -m pytest tests/ -v --tb=short
if %errorlevel% neq 0 (
    echo [警告] 部分测试未通过，继续构建...
)

echo [2/5] 创建虚拟环境...
python -m venv build_env
call build_env\Scripts\activate.bat

echo [3/5] 安装依赖...
pip install --upgrade pip
pip install PySide6 python-docx kenlm pycorrector jieba pypinyin loguru tqdm pyinstaller
pip install torch transformers --index-url https://download.pytorch.org/whl/cpu

echo [4/5] 构建便携版（含 MacBERT 引擎支持）...

REM Handle missing icon
set ICON_ARG=
if exist "docproof\resources\icon.ico" (
    set ICON_ARG=--icon="docproof\resources\icon.ico"
    echo   使用应用图标: docproof\resources\icon.ico
) else (
    echo   未找到图标文件，使用默认图标
)

pyinstaller --noconfirm ^
    --name="DocProof" ^
    --windowed ^
    --onedir ^
    %ICON_ARG% ^
    --add-data="third_party/pycorrector/pycorrector;pycorrector" ^
    --add-data="models;models" ^
    --hidden-import="pycorrector" ^
    --hidden-import="pycorrector.macbert" ^
    --hidden-import="pycorrector.macbert.macbert_corrector" ^
    --hidden-import="pycorrector.corrector" ^
    --hidden-import="pycorrector.detector" ^
    --hidden-import="pycorrector.proper_corrector" ^
    --hidden-import="pycorrector.utils" ^
    --hidden-import="pycorrector.utils.text_utils" ^
    --hidden-import="pycorrector.utils.tokenizer" ^
    --hidden-import="pycorrector.utils.get_file" ^
    --hidden-import="pycorrector.utils.error_utils" ^
    --hidden-import="kenlm" ^
    --hidden-import="pypinyin" ^
    --hidden-import="jieba" ^
    --hidden-import="transformers" ^
    --hidden-import="transformers.models.bert" ^
    --hidden-import="transformers.models.bert.modeling_bert" ^
    --hidden-import="transformers.models.bert.tokenization_bert" ^
    --hidden-import="torch" ^
    --hidden-import="torch.nn" ^
    --hidden-import="loguru" ^
    --hidden-import="tqdm" ^
    --collect-all="pycorrector" ^
    docproof\__main__.py

if %errorlevel% neq 0 (
    echo [错误] 构建失败！
    pause
    exit /b 1
)

echo [5/5] 整理便携版目录...
if exist "dist\DocProof-portable" rmdir /s /q "dist\DocProof-portable"
rename "dist\DocProof" "DocProof-portable"

REM Create empty models dir if not copied
if not exist "dist\DocProof-portable\models" mkdir "dist\DocProof-portable\models"

REM Copy launch instructions
(
echo DocProof 便携版使用说明
echo ========================
echo.
echo 支持两种校对引擎:
echo   1. Kenlm 统计模型 — 开箱即用，需放入 .klm 文件到 models/
echo   2. MacBERT 深度学习 — 首次使用自动下载模型 (~400MB) 到 models/macbert_cache/
echo.
echo Kenlm 模型下载:
echo   标准模型(141MB): https://github.com/shibing624/pycorrector/releases/download/1.0.0/people2014corpus_chars.klm
echo   大型模型(2.95GB): https://deepspeech.bj.bcebos.com/zh_lm/zh_giga.no_cna_cmn.prune01244.klm
echo.
echo 放入 models/ 目录后双击 DocProof.exe 启动。
echo MacBERT 引擎需先安装 PyTorch（已内置），首次切换会自动下载模型。
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
