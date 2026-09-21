# Procedimento interno de gestão de mudanças

- **Document ID:** DOC-024
- **Version:** 2.4
- **Date:** 2026-07-06
- **Status:** current
- **Language:** pt-BR

## Classes de mudança
`DOC-024#SEC-01`

Mudança padrão é repetível, pré-aprovada e segue instrução testada. Mudança normal exige análise de risco e janela. Mudança emergencial usa o prefixo CHG-EMR- e existe para reduzir impacto ativo ou risco iminente. Urgência comercial, sozinha, não transforma uma alteração em emergencial.

## Aprovações
`DOC-024#SEC-02`

A mudança normal precisa de responsável técnico e aprovador distinto. Alterações em autenticação, retenção ou região exigem Security Admin. Mudança emergencial pode ser autorizada pelo Incident Commander durante P1 ou P2, mas deve receber revisão independente no próximo dia útil.

## Plano e execução
`DOC-024#SEC-03`

O registro deve conter objetivo, escopo, hipótese de risco, validação, rollback, janela e comunicação. Execute uma alteração material por vez. Preserve métricas anteriores e posteriores. Se o critério de validação falhar, inicie rollback ou documente por que continuar reduz mais risco.

## Fechamento
`DOC-024#SEC-04`

Registre resultado, desvios, evidências e tarefas posteriores. Mudanças ligadas a incidentes devem apontar para o postmortem. Um ticket fechado sem evidência de validação é devolvido. A revisão mensal procura repetição de emergências e oportunidades de transformar procedimentos maduros em mudanças padrão.

## Público e pré-requisitos
`DOC-024#SEC-05`

Este documento é destinado a pessoas que operam ou administram a OrbeFlow e já conhecem workspace, ambiente e os identificadores básicos da plataforma. A leitura pressupõe acesso autorizado aos registros citados, nunca acesso ampliado apenas para investigação. O foco específico é responsabilidade, aprovação, evidência e tratamento de exceções. Antes de agir, confirme se o workspace é de produção ou sandbox, qual plano está ativo e qual revisão ou versão aparece na evidência. O mesmo nome visual pode existir em ambientes diferentes. Copiar uma ação de sandbox para produção sem nova validação não é permitido. Quando a atividade exigir um papel que o leitor não possui, preserve as evidências e encaminhe para o responsável, sem tentar contornar o Access Gate.

## Evidências mínimas
`DOC-024#SEC-06`

Registre horário em UTC, região, workspace, ambiente, identificadores relevantes e o resultado observado. Para execuções, combine event_id, RUN-, workflow_id e revisão; para tarefas, inclua TSK- e estado; para conexões, inclua CON- e fornecedor, sem segredos. Códigos como PX-1047 ou RL-4290 devem ser copiados exatamente. Uma captura isolada pode omitir detalhes, portanto prefira exportação redigida ou campos estruturados. A ausência de um identificador deve ser declarada, não preenchida por inferência. Evidências pessoais ou comerciais que não contribuam para o diagnóstico devem ser removidas. O registro final precisa permitir que outra pessoa repita a análise sem depender da memória de quem iniciou o caso.

## Exemplo operacional
`DOC-024#SEC-07`

Considere uma solicitação relacionada a “Procedimento interno de gestão de mudanças”. O operador primeiro delimita período e ambiente, depois localiza o objeto pelo identificador e compara o comportamento esperado com o observado. Se houver diferença, registra uma hipótese por vez e escolhe a verificação de menor risco. Uma resposta sem código pode ser semanticamente parecida com vários artigos; por isso, o contexto do objeto e o estado atual são decisivos. Se a evidência apontar para outro domínio, o caso deve migrar com o histórico preservado. Repetir a operação com novos identificadores antes de compreender idempotência pode criar ruído, duplicidade externa ou perda de rastreabilidade.

## Limites e exceções
`DOC-024#SEC-08`

Este documento não autoriza mudanças de plano, redução de controles, exclusão de registros ou acesso a conteúdo não redigido. Valores comerciais e limites operacionais devem ser confirmados no catálogo vigente, mesmo quando uma nota histórica apresenta números. Uma exceção precisa de justificativa, prazo, responsável e aprovação compatível com o risco. Situações ligadas a autenticação, retenção ou residência de dados exigem participação de Security Admin. Durante incidente, a aprovação emergencial pode acelerar a mitigação, mas não elimina revisão posterior. Se duas fontes atuais parecerem incompatíveis, interrompa a ação e registre a divergência para correção documental.

## Validação e documentos relacionados
`DOC-024#SEC-09`

Conclua verificando se o resultado esperado realmente ocorreu e se não houve efeito colateral em outro módulo. Para mudanças, compare uma janela anterior e uma posterior; para suporte, reproduza apenas quando isso for seguro; para políticas, confirme versão e data efetiva. Os documentos relacionados mais úteis são DOC-012, DOC-013, DOC-014. A relação indica contexto, não precedência automática. Em conflito, uma política vigente supera um guia operacional, o catálogo vigente supera release notes históricas e a evidência do objeto supera suposições baseadas em nome. Registre o identificador da seção utilizada, pois futuras avaliações devem distinguir uma recuperação correta de um trecho apenas semanticamente próximo.
