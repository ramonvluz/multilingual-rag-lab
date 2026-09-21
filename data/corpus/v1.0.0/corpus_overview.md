# Multilingual RAG Lab Corpus

## Universo fictício

**Empresa:** Nuvexa Sistemas  
**Produto:** OrbeFlow

Nuvexa Sistemas oferece a OrbeFlow, uma plataforma B2B de automação operacional orientada a eventos. Seus módulos são Flow Studio, Relay Hub, Access Gate, Insight Board e Vault Records. Os objetos centrais são workflows, revisões, eventos, execuções RUN-, tarefas TSK- e conexões CON-. Os planos comerciais são Starter, Growth e Enterprise; API-V3 é a versão atual.

## Composição

O corpus contém 24 documentos sintéticos: 12 em PT-BR, 8 em inglês e 4 em espanhol. Há documentação de produto, suporte, segurança, operações, releases, planos e SLA, incidentes e políticas. Os formatos são Markdown, HTML, DOCX, PDF, CSV e XLSX.

## Dificuldades deliberadas

- paráfrases e sinônimos para recuperação semântica;
- códigos, endpoints, versões e identificadores que favorecem recuperação lexical;
- perguntas mistas que exigem intenção e termo exato;
- documentos próximos sobre login, política de autenticação e recuperação de MFA;
- informações históricas superadas nas versões 2.3 e 2.4;
- respostas que dependem de mais de um documento;
- conhecimento distribuído entre idiomas para recuperação cross-lingual;
- lacunas intencionais, permitindo perguntas sem resposta.

O arquivo `manifest.json` registra IDs estáveis, seções, relações e anotações para criação posterior do golden dataset. Não há métricas nem resultados simulados de retrieval.
