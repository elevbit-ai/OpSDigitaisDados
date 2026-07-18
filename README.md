# OpS Digitais Dados

**Leitor de impressão digital e registrador de banco de dados interno**  
com **exportação (download)** e **importação (upload)** de tudo salvo.

por **Joaquim Pedro de Morais Filho**

| | |
|---|---|
| Website | [usacomment.com](https://usacomment.com) |
| E-mail | zicutake@mail.ru |
| Versão | 1.0.0 |
| PC | `C:\Users\franc\OpSDigitaisDados` |
| GitHub | https://github.com/elevbit-ai/OpSDigitaisDados |

## Recursos

- Cadastro de usuários no **banco SQLite interno**
- Registro de **impressão digital** (imagem de scanner → template ORB)
- **Identificação 1:N** no banco local
- **Exportar tudo** → ZIP (`ops_digitais_dados.db` + previews + manifest)
- **Importar / upload** do ZIP (com backup `.bak`)
- Website + tutorial + EXE Windows

## Executar

```powershell
cd C:\Users\franc\OpSDigitaisDados
python -m pip install -r requirements.txt
python app\main.py
```

## EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

Saída: `dist\OpSDigitaisDados\OpSDigitaisDados.exe`

## Website

- Local: `website/index.html` e `website/tutorial.html`
- **GitHub Pages:** https://elevbit-ai.github.io/OpSDigitaisDados/

## Imagens demo (teste de digital)

Pasta no PC e no repositório:

```
C:\Users\franc\OpSDigitaisDados\sample_prints\
```

| Arquivo | Uso |
|---------|-----|
| `demo_a.png` | Digital de teste (usuário A) |
| `demo_a2.png` | Mesma digital A (deve identificar) |
| `demo_b.png` | Outra digital (usuário B) |
| `backup_test.zip` | Exemplo de pacote exportado |

## Privacidade

Dados biométricos e cadastrais ficam **somente no PC**. Não há envio automático à nuvem.  
Faça backup com **Exportar tudo**.

## Licença

MIT — Joaquim Pedro de Morais Filho (2026)
