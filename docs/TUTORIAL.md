# Tutorial — OpS Digitais Dados

**Autor:** Joaquim Pedro de Morais Filho  
**Site:** https://usacomment.com  
**E-mail:** zicutake@mail.ru  

## Executar

```powershell
cd C:\Users\franc\OpSDigitaisDados
python -m pip install -r requirements.txt
python app\main.py
```

EXE: `dist\OpSDigitaisDados\OpSDigitaisDados.exe`

## Funções

1. Cadastrar / editar / excluir usuários  
2. Registrar impressão digital (imagem)  
3. Identificar digital no banco (1:N)  
4. **Exportar tudo** (download ZIP)  
5. **Importar / upload** do ZIP  

## Banco local

`data\ops_digitais_dados.db`  
Pré-visualizações: `data\previews\`

## Build EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```
