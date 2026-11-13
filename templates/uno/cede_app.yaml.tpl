application_id: "{{app_name}}"
target: uno
category: {{category}}
entrypoint: "build/{{app_name}}.hex"
resources:
  usb_serial:
    banner_prefix: "CEDE {{app_name}} ok"
