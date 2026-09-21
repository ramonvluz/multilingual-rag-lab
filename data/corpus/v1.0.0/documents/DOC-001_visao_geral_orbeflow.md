# Visão geral da plataforma OrbeFlow

- **Document ID:** DOC-001
- **Version:** 3.0
- **Date:** 2026-06-12
- **Status:** current
- **Language:** pt-BR

## Finalidade e escopo
`DOC-001#SEC-01`

A OrbeFlow é uma plataforma B2B de automação operacional criada pela Nuvexa Sistemas. Ela recebe eventos de sistemas corporativos, aplica regras versionadas, distribui tarefas e registra evidências de execução. A plataforma não substitui o sistema de origem: pedidos, contratos e cadastros continuam pertencendo aos aplicativos que os criaram. A OrbeFlow coordena o trabalho entre eles.

O produto atende operações que precisam combinar integrações por API, decisões determinísticas e revisão humana. Exemplos comuns incluem validar pedidos antes do faturamento, encaminhar divergências cadastrais e acompanhar aprovações com prazo. O ambiente de cada cliente é chamado de workspace.

## Módulos principais
`DOC-001#SEC-02`

Flow Studio permite desenhar fluxos com gatilhos, regras, etapas e rotas de exceção. Relay Hub administra conexões, webhooks e filas de entrega. Access Gate concentra identidade, MFA e permissões. Insight Board mostra volume, duração, falhas e backlog. Vault Records guarda anexos e evidências associados a uma execução.

Uma automação é um fluxo publicado. Cada processamento desse fluxo cria uma execução, identificada por RUN- seguido de 12 caracteres. Uma atividade que exige ação humana cria uma tarefa, identificada por TSK-. Conexões externas usam o prefixo CON-. Esses termos não são intercambiáveis: uma execução pode gerar várias tarefas e usar várias conexões.

## Ciclo de uma execução
`DOC-001#SEC-03`

Um evento aceito recebe um event_id e entra no estado RECEIVED. Após validar o esquema, a OrbeFlow cria a execução em QUEUED. O motor passa por RUNNING e termina em SUCCEEDED, FAILED, CANCELLED ou WAITING_REVIEW. WAITING_REVIEW não é falha: indica que uma regra pediu decisão humana.

Eventos duplicados com a mesma chave de idempotência dentro da janela aplicável não criam uma segunda execução. O registro duplicado aponta para o RUN- original. A duração da janela depende do plano e deve ser confirmada no catálogo de limites, não neste documento.

## Princípios de uso
`DOC-001#SEC-04`

Regras críticas devem ser explícitas e testáveis. Decisões de acesso nunca devem depender de texto gerado. Segredos ficam em conexões gerenciadas e não em variáveis de fluxo. Publicar uma nova revisão não altera execuções já iniciadas. Para investigar falhas, use o run_id, o código de erro e a revisão do fluxo em conjunto.

## Público e pré-requisitos
`DOC-001#SEC-05`

Este documento é destinado a pessoas que operam ou administram a OrbeFlow e já conhecem workspace, ambiente e os identificadores básicos da plataforma. A leitura pressupõe acesso autorizado aos registros citados, nunca acesso ampliado apenas para investigação. O foco específico é comportamento funcional, objetos do produto e limites entre módulos. Antes de agir, confirme se o workspace é de produção ou sandbox, qual plano está ativo e qual revisão ou versão aparece na evidência. O mesmo nome visual pode existir em ambientes diferentes. Copiar uma ação de sandbox para produção sem nova validação não é permitido. Quando a atividade exigir um papel que o leitor não possui, preserve as evidências e encaminhe para o responsável, sem tentar contornar o Access Gate.

## Evidências mínimas
`DOC-001#SEC-06`

Registre horário em UTC, região, workspace, ambiente, identificadores relevantes e o resultado observado. Para execuções, combine event_id, RUN-, workflow_id e revisão; para tarefas, inclua TSK- e estado; para conexões, inclua CON- e fornecedor, sem segredos. Códigos como PX-1047 ou RL-4290 devem ser copiados exatamente. Uma captura isolada pode omitir detalhes, portanto prefira exportação redigida ou campos estruturados. A ausência de um identificador deve ser declarada, não preenchida por inferência. Evidências pessoais ou comerciais que não contribuam para o diagnóstico devem ser removidas. O registro final precisa permitir que outra pessoa repita a análise sem depender da memória de quem iniciou o caso.

## Exemplo operacional
`DOC-001#SEC-07`

Considere uma solicitação relacionada a “Visão geral da plataforma OrbeFlow”. O operador primeiro delimita período e ambiente, depois localiza o objeto pelo identificador e compara o comportamento esperado com o observado. Se houver diferença, registra uma hipótese por vez e escolhe a verificação de menor risco. Uma resposta sem código pode ser semanticamente parecida com vários artigos; por isso, o contexto do objeto e o estado atual são decisivos. Se a evidência apontar para outro domínio, o caso deve migrar com o histórico preservado. Repetir a operação com novos identificadores antes de compreender idempotência pode criar ruído, duplicidade externa ou perda de rastreabilidade.

## Limites e exceções
`DOC-001#SEC-08`

Este documento não autoriza mudanças de plano, redução de controles, exclusão de registros ou acesso a conteúdo não redigido. Valores comerciais e limites operacionais devem ser confirmados no catálogo vigente, mesmo quando uma nota histórica apresenta números. Uma exceção precisa de justificativa, prazo, responsável e aprovação compatível com o risco. Situações ligadas a autenticação, retenção ou residência de dados exigem participação de Security Admin. Durante incidente, a aprovação emergencial pode acelerar a mitigação, mas não elimina revisão posterior. Se duas fontes atuais parecerem incompatíveis, interrompa a ação e registre a divergência para correção documental.

## Validação e documentos relacionados
`DOC-001#SEC-09`

Conclua verificando se o resultado esperado realmente ocorreu e se não houve efeito colateral em outro módulo. Para mudanças, compare uma janela anterior e uma posterior; para suporte, reproduza apenas quando isso for seguro; para políticas, confirme versão e data efetiva. Os documentos relacionados mais úteis são DOC-002, DOC-003, DOC-018. A relação indica contexto, não precedência automática. Em conflito, uma política vigente supera um guia operacional, o catálogo vigente supera release notes históricas e a evidência do objeto supera suposições baseadas em nome. Registre o identificador da seção utilizada, pois futuras avaliações devem distinguir uma recuperação correta de um trecho apenas semanticamente próximo.
