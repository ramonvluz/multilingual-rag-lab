# Golden Dataset V1 — auditoria

## Metodologia

Fonte: `data/corpus/v1.0.0` (manifesto e conteúdo dos 24 documentos). As respostas foram confrontadas com as seções indicadas abaixo; IDs de seção são trilha de auditoria, não unidade de scoring. Relevância é binária por documento, sem graduar ganhos nDCG. Não foi executada nenhuma variante nem calculada métrica de retrieval. As 4 perguntas sem resposta ficam fora das métricas positivas e se destinam a avaliação posterior de abstenção.

## Contagem e distribuição

| Tipo principal | Queries |
|---|---:|
| semantic | 8 |
| exact | 6 |
| mixed | 6 |
| cross_lingual | 8 |
| multi_context | 6 |
| versioning | 6 |
| ambiguous | 4 |
| unanswerable | 4 |

**Total: 48; IDs Q-001 a Q-048, únicos e sequenciais.** 44 answerable; 4 unanswerable.

## Idiomas

| Idioma da pergunta | Quantidade |
|---|---:|
| pt-BR | 23 |
| en | 15 |
| es | 10 |

### Matriz pergunta → idioma da evidência

A matriz principal inclui somente as 35 consultas com um documento relevante; as 9 consultas com múltiplos documentos são descritas em seguida para evitar atribuir artificialmente um idioma principal.

| Pergunta | Evidência pt-BR | Evidência en | Evidência es |
|---|---:|---:|---:|
| pt-BR | 12 | 2 | 3 |
| en | 3 | 7 | 1 |
| es | 2 | 1 | 4 |

As 8 consultas `cross_lingual` são Q-021–Q-028: PT→EN (1), PT→ES (2), EN→PT (2), EN→ES (1), ES→PT (1), ES→EN (1). Cada evidência oficial difere do idioma da pergunta.

Consultas com múltiplas evidências: Q-029 PT+PT; Q-030 EN+PT; Q-031 ES+ES; Q-032 EN+EN; Q-033 PT+EN; Q-034 ES+PT; Q-038 PT+EN+PT; Q-039 PT+PT+EN; Q-040 EN+PT.

## Cobertura documental

| Documento | Relevâncias | Documento | Relevâncias |
|---|---:|---|---:|
| DOC-001 | 2 | DOC-013 | 2 |
| DOC-002 | 2 | DOC-014 | 3 |
| DOC-003 | 3 | DOC-015 | 3 |
| DOC-004 | 3 | DOC-016 | 3 |
| DOC-005 | 2 | DOC-017 | 3 |
| DOC-006 | 2 | DOC-018 | 3 |
| DOC-007 | 3 | DOC-019 | 1 |
| DOC-008 | 2 | DOC-020 | 2 |
| DOC-009 | 3 | DOC-021 | 1 |
| DOC-010 | 3 | DOC-022 | 1 |
| DOC-011 | 2 | DOC-023 | 2 |
| DOC-012 | 3 | DOC-024 | 1 |

Todos os 24 documentos aparecem pelo menos uma vez. DOC-019, DOC-021, DOC-022 e DOC-024 aparecem uma vez; nenhum aparece mais de três vezes. Esta cobertura resulta de perguntas justificadas pelo conteúdo, sem inclusão de documentos apenas relacionados.

## Cardinalidade e casos especiais

- 35 consultas com um documento relevante; 9 com dois ou mais; 4 sem documento (unanswerable).
- Multi-context Q-029–Q-034 exige combinar exatamente dois documentos. Q-038–Q-040 também usam múltiplos documentos por comparação temporal.
- Unanswerable: Q-045 SDK móvel; Q-046 instalação on-premises; Q-047 impostos na fatura; Q-048 atendimento por chamada de voz. Todas têm `relevant_documents: []`.
- Versioning: Q-035 ancora 2.3 em DOC-015; Q-036 ancora preview 2.4 em DOC-016; Q-037 usa GA 2.5.1 em DOC-017; Q-038 compara 2.3/2.4/catálogo atual; Q-039 compara sessão antiga, mudança e política vigente; Q-040 compara agendamento optativo 2.4 e obrigatório 2.5.

## Revisão de ground truth

| Query | Seção ou seções que sustentam a resposta |
|---|---|
| Q-001 | DOC-001#SEC-01 |
| Q-002 | DOC-002#SEC-04 |
| Q-003 | DOC-003#SEC-01 |
| Q-004 | DOC-004#SEC-01 |
| Q-005 | DOC-005#SEC-02 |
| Q-006 | DOC-007#SEC-02 |
| Q-007 | DOC-008#SEC-01 |
| Q-008 | DOC-021#SEC-03 |
| Q-009 | DOC-006#SEC-01 |
| Q-010 | DOC-010#SEC-03 |
| Q-011 | DOC-011#SEC-01 |
| Q-012 | DOC-018#SEC-01 |
| Q-013 | DOC-020#SEC-01 |
| Q-014 | DOC-024#SEC-02/03 |
| Q-015 | DOC-005#SEC-03 |
| Q-016 | DOC-006#SEC-02 |
| Q-017 | DOC-007#SEC-03 |
| Q-018 | DOC-008#SEC-03 |
| Q-019 | DOC-012#SEC-02/03 |
| Q-020 | DOC-022#SEC-03 |
| Q-021 | DOC-009#SEC-02 |
| Q-022 | DOC-014#SEC-03 |
| Q-023 | DOC-010#SEC-02 |
| Q-024 | DOC-013#SEC-03 |
| Q-025 | DOC-023#SEC-02 |
| Q-026 | DOC-004#SEC-02 |
| Q-027 | DOC-020#SEC-01 |
| Q-028 | DOC-012#SEC-02/03 |
| Q-029 | DOC-001#SEC-03 + DOC-003#SEC-01 |
| Q-030 | DOC-002#SEC-02 + DOC-018#SEC-01 |
| Q-031 | DOC-004#SEC-03 + DOC-014#SEC-03 |
| Q-032 | DOC-009#SEC-02 + DOC-011#SEC-01 |
| Q-033 | DOC-013#SEC-02 + DOC-019#SEC-02 |
| Q-034 | DOC-014#SEC-04 + DOC-023#SEC-02/03 |
| Q-035 | DOC-015#SEC-01 |
| Q-036 | DOC-016#SEC-01 |
| Q-037 | DOC-017#SEC-01 |
| Q-038 | DOC-015#SEC-03 + DOC-016#SEC-03 + DOC-018#SEC-01 |
| Q-039 | DOC-015#SEC-02 + DOC-017#SEC-03 + DOC-009#SEC-02 |
| Q-040 | DOC-016#SEC-02 + DOC-017#SEC-02 |
| Q-041 | DOC-012#SEC-01/02/03 |
| Q-042 | DOC-010#SEC-01/02 |
| Q-043 | DOC-003#SEC-01 |
| Q-044 | DOC-007#SEC-02 |

## Duplicidade, vazamento lexical e correções

- Revisão manual por intenção, entidade, resultado esperado e documento: nenhum par exige a mesma resposta pelo mesmo caminho. Os pares próximos são deliberados: Q-005/Q-042 (senha/SSO versus perda do fator), Q-019/Q-041 (procedimento de entrega com e sem discriminação ambígua), Q-022/Q-026 (migração versus persistência no ponto de presença), Q-035/Q-038 (limite histórico isolado versus evolução histórica).
- A cópia literal de títulos foi evitada. Códigos, cabeçalhos, endpoint e versões são mantidos intencionalmente nos testes exact, mixed e versioning. As perguntas semânticas usam cenários e paráfrases.
- Ajustes na revisão: a pergunta de versão atual da API foi ancorada apenas em DOC-017, sem adicionar o preview por proximidade; a janela vigente Growth foi atribuída a DOC-018, não às release notes antigas; a pergunta de payload cru combina a permissão explícita de DOC-011 com a exigência temporal de DOC-009; os quatro gaps ficaram sem documento positivo.

**Resultado:** schema, IDs, contagens, idiomas, cardinalidade, referências e evidências seções validados; sem inconsistências pendentes identificadas. A qualidade de recuperação e abstenção permanece não medida.
