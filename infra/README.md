# The download site's AWS resources

`site.yaml` is a CloudFormation stack with everything the download site needs:

- a **private S3 bucket** (no public access, SSE-S3, versioning with old versions expiring
  after 30 days) holding the site (`site/`), the installers (`releases/<v>/`, `download/`) and
  `latest.json`;
- a **CloudFront distribution** that reads it through an Origin Access Control, over HTTPS
  only, with security headers (a CSP that allows only the site itself) and `/404.html` for
  missing pages;
- the **GitHub OIDC provider** and the **`peao-bilingue-release` role**, which GitHub Actions
  assumes with no stored key. It trusts only this repository's version tags (`v*`, the release
  workflow) and `main` (the site workflow), and may only write to this bucket and invalidate
  this distribution;
- a **US$ 5 monthly budget** that emails you at 80% of the actual cost and at 100% of the
  forecast. It watches the whole account, not only this stack.

The bucket is **kept when the stack is deleted** (`DeletionPolicy: Retain`): it holds every
published version.

## Creating the stack

With AWS credentials for the account (an administrator, or someone allowed to create IAM roles):

```bash
aws cloudformation deploy --template-file infra/site.yaml --stack-name peao-bilingue-site --region us-east-1 --capabilities CAPABILITY_NAMED_IAM --parameter-overrides BudgetEmail=you@example.com
```

us-east-1 because CloudFront only takes ACM certificates from there, which matters for a custom
domain later. Parameters:

| Parameter | Default | What it is |
|---|---|---|
| `BudgetEmail` | (required) | Who gets the budget alerts. No confirmation is needed. |
| `BudgetLimitUsd` | `5` | The monthly cost, for the whole account, that triggers them. |
| `GitHubRepository` | `gvieiragoulart/peao-bilingue` | The repository whose workflows may publish. |
| `CreateOidcProvider` | `true` | `false` if the account already has the `token.actions.githubusercontent.com` provider (`aws iam list-open-id-connect-providers`): an account can have only one. |
| `DomainName`, `CertificateArn` | empty | A custom domain, for later (below). |
| `WebAclArn` | empty | The web ACL of a CloudFront flat-rate plan, for later (below). |

## Wiring GitHub to it

```bash
aws cloudformation describe-stacks --stack-name peao-bilingue-site --region us-east-1 --query "Stacks[0].Outputs" --output table
```

The outputs become **repository variables** (GitHub → the repository → Settings → Secrets and
variables → Actions → *Variables*: they aren't secrets, since the role only trusts this
repository's workflows):

| Output | Variable |
|---|---|
| `ReleaseRoleArn` | `AWS_RELEASE_ROLE_ARN` |
| `BucketName` | `SITE_BUCKET` |
| `DistributionId` | `SITE_DISTRIBUTION_ID` |
| `SiteUrl` | `SITE_URL` |

`SiteUrl` (`https://dxxxx.cloudfront.net`) also goes into the code, replacing
`https://REPLACE-WITH-CLOUDFRONT-DOMAIN.cloudfront.net` in `src/peao_bilingue/config.py`
(`SITE_URL`: every installed version checks for updates there) and in the README's download
link. The release workflow refuses to build while the placeholder is anywhere, or while
`config.py` disagrees with the variable.

Then publish the site once: Actions → Site → *Run workflow* (from then on it runs on every push
to `main` that changes `site/`). The first release is a tag: see "The .exe" in the README.

## Cost

- **S3**: cents (a few installers of ~60 MB each, the old versions expiring after 30 days).
- **CloudFront**: pay-as-you-go by default. The traffic from S3 to CloudFront is free; what
  reaches the visitors is charged per GB and per request, after the free tier.
- **Flat-rate plan (optional):** CloudFront's *Free* plan costs US$ 0 a month, with 1 M
  requests and 100 GB of data transfer a month. There are **no overage charges**: sustained,
  substantial excess over months may only slow the delivery down, and the first spike up to 3×
  the allowance is accommodated. Source: [CloudFront flat-rate pricing
  plans](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/flat-rate-pricing-plan.html).
  What the docs say, and what it means here:
  - The subscription is made in the **CloudFront console** (edit the distribution → choose the
    pricing plan), or through the CLI / the PricingPlanManager API. It is **not** a
    CloudFormation property.
  - A plan needs an **AWS WAF web ACL** attached to the distribution (it is included in the
    plan). After subscribing, copy the web ACL's ARN (the distribution's *Security* tab) into
    the stack, or the next stack update would detach it:

    ```bash
    aws cloudformation deploy --template-file infra/site.yaml --stack-name peao-bilingue-site --region us-east-1 --capabilities CAPABILITY_NAMED_IAM --parameter-overrides BudgetEmail=you@example.com WebAclArn=arn:aws:wafv2:us-east-1:...
    ```

  - This distribution already uses only what plans support: an OAC (not the legacy OAI), cache
    and response-headers policies (no `ForwardedValues`), no real-time logs, no functions.
  - Accounts **still on the AWS Free Tier** can't subscribe; there are at most 3 free plans per
    account.
  - A distribution on a plan can't be deleted: cancel the plan first (a free one is cancelled
    immediately).

## A custom domain, later

1. Register it (e.g. at registro.br) and request a public certificate for it in **ACM, in
   us-east-1**, validated by DNS.
2. Update the stack with `DomainName=peaobilingue.com.br CertificateArn=arn:aws:acm:us-east-1:...`
   (plus the other parameters you set before). The domain becomes an alias **of the same
   distribution**.
3. Point the domain at the distribution: an ALIAS (Route 53) or CNAME record to
   `dxxxx.cloudfront.net`.

The `dxxxx.cloudfront.net` address **keeps working**: the versions already installed check for
updates there, so `SITE_URL` in `config.py` and the `SITE_URL` variable stay as they are. Only the
site's own links and the README may switch to the new domain.

## Deleting it

The bucket is retained. To remove everything: cancel the flat-rate plan, if any; delete the
stack (`aws cloudformation delete-stack --stack-name peao-bilingue-site --region us-east-1`);
then empty the bucket, including its old versions (the console's *Empty* button does both), and
delete it. Every installed copy of the app then stops finding updates, quietly.
