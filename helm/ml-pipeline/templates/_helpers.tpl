{{/*
Common labels for all resources.
*/}}
{{- define "ml-pipeline.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: ml-pipeline
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Kafka bootstrap servers — either from self-hosted or external (MSK).
*/}}
{{- define "ml-pipeline.kafkaBootstrapServers" -}}
{{ .Values.kafka.bootstrapServers }}
{{- end }}
