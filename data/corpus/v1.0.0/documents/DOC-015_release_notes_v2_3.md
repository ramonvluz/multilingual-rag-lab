# Notas da versão 2.3

- **Document ID:** DOC-015
- **Version:** 2.3.0
- **Date:** 2025-11-18
- **Status:** superseded
- **Language:** pt-BR

## Destaques
`DOC-015#SEC-01`

A versão 2.3 introduziu tarefas humanas com prazo, exportação de execuções e chaves de idempotência para API-V2. Workspaces Growth passaram a ter janela de idempotência de 24 horas. Enterprise passou a ter janela de 72 horas.

## Autenticação
`DOC-015#SEC-02`

A duração máxima de sessão interativa foi definida em 30 dias, com expiração por inatividade em 12 horas. Administradores receberam a opção de exigir MFA por workspace. Esta configuração não era automática para operadores existentes.

## Limites publicados
`DOC-015#SEC-03`

O endpoint de criação aceitava 300 requisições por minuto no Growth e 1.200 no Enterprise. Reprocessamento em lote permitia 100 execuções no Growth e 1.000 no Enterprise. Esses valores pertencem à versão 2.3 e não devem ser usados como catálogo atual.

## Correções
`DOC-015#SEC-04`

Corrigido o caso em que uma tarefa vencida permanecia visível como aberta depois de a rota de timeout concluir. Adicionado request_id às respostas PX-1047.

## Público e pré-requisitos
`DOC-015#SEC-05`

Este documento é destinado a pessoas que operam ou administram a OrbeFlow e já conhecem workspace, ambiente e os identificadores básicos da plataforma. A leitura pressupõe acesso autorizado aos registros citados, nunca acesso ampliado apenas para investigação. O foco específico é mudanças da versão, compatibilidade e separação entre histórico e estado atual. Antes de agir, confirme se o workspace é de produção ou sandbox, qual plano está ativo e qual revisão ou versão aparece na evidência. O mesmo nome visual pode existir em ambientes diferentes. Copiar uma ação de sandbox para produção sem nova validação não é permitido. Quando a atividade exigir um papel que o leitor não possui, preserve as evidências e encaminhe para o responsável, sem tentar contornar o Access Gate.

## Evidências mínimas
`DOC-015#SEC-06`

Registre horário em UTC, região, workspace, ambiente, identificadores relevantes e o resultado observado. Para execuções, combine event_id, RUN-, workflow_id e revisão; para tarefas, inclua TSK- e estado; para conexões, inclua CON- e fornecedor, sem segredos. Códigos como PX-1047 ou RL-4290 devem ser copiados exatamente. Uma captura isolada pode omitir detalhes, portanto prefira exportação redigida ou campos estruturados. A ausência de um identificador deve ser declarada, não preenchida por inferência. Evidências pessoais ou comerciais que não contribuam para o diagnóstico devem ser removidas. O registro final precisa permitir que outra pessoa repita a análise sem depender da memória de quem iniciou o caso.

## Exemplo operacional
`DOC-015#SEC-07`

Considere uma solicitação relacionada a “Notas da versão 2.3”. O operador primeiro delimita período e ambiente, depois localiza o objeto pelo identificador e compara o comportamento esperado com o observado. Se houver diferença, registra uma hipótese por vez e escolhe a verificação de menor risco. Uma resposta sem código pode ser semanticamente parecida com vários artigos; por isso, o contexto do objeto e o estado atual são decisivos. Se a evidência apontar para outro domínio, o caso deve migrar com o histórico preservado. Repetir a operação com novos identificadores antes de compreender idempotência pode criar ruído, duplicidade externa ou perda de rastreabilidade.

## Limites e exceções
`DOC-015#SEC-08`

Este documento não autoriza mudanças de plano, redução de controles, exclusão de registros ou acesso a conteúdo não redigido. Valores comerciais e limites operacionais devem ser confirmados no catálogo vigente, mesmo quando uma nota histórica apresenta números. Uma exceção precisa de justificativa, prazo, responsável e aprovação compatível com o risco. Situações ligadas a autenticação, retenção ou residência de dados exigem participação de Security Admin. Durante incidente, a aprovação emergencial pode acelerar a mitigação, mas não elimina revisão posterior. Se duas fontes atuais parecerem incompatíveis, interrompa a ação e registre a divergência para correção documental.

## Validação e documentos relacionados
`DOC-015#SEC-09`

Conclua verificando se o resultado esperado realmente ocorreu e se não houve efeito colateral em outro módulo. Para mudanças, compare uma janela anterior e uma posterior; para suporte, reproduza apenas quando isso for seguro; para políticas, confirme versão e data efetiva. Os documentos relacionados mais úteis são DOC-009, DOC-016, DOC-017. A relação indica contexto, não precedência automática. Em conflito, uma política vigente supera um guia operacional, o catálogo vigente supera release notes históricas e a evidência do objeto supera suposições baseadas em nome. Registre o identificador da seção utilizada, pois futuras avaliações devem distinguir uma recuperação correta de um trecho apenas semanticamente próximo.
