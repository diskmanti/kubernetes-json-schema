# Kubernetes CRDs json schema

This repository aggregates popular Kubernetes CRDs (`CustomResourceDefinition`) in JSON schema format. These schemas can be used by various tools such as [Kubeconform](https://github.com/yannh/kubeconform).
Running Kubernetes schema validation checks helps apply the **"shift-left approach"** on machines **without** giving them access to your cluster (e.g. locally or on CI).

## How to use the schemas

### Kubeconform

```
kubeconform -schema-location default -schema-location 'https://raw.githubusercontent.com/diskmanti/diskmanti/kubernetes-json-schema/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' [MANIFEST]
```
