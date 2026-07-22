# Brand configuration

The public repository ships with `brand-profile-example-v0.1.json`. Its fixed footer is disabled, so generated previews never include an unknown logo, QR code, or company CTA.

To use a private brand profile, copy the example outside version control, configure the footer asset with a local path, and set:

```powershell
$env:VISUAL_DIRECTOR_BRAND_PROFILE="C:\private\brand-profile.json"
```

Restart the API after changing the profile. Never commit QR codes, account credentials, private logos, or assets without redistribution permission.
