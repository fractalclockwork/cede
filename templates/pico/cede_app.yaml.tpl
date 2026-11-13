application_id: "{{app_name}}"
target: pico
category: {{category}}
entrypoint: "build/{{app_name}}.uf2"
resources:
  usb_serial:
    banner_prefix: "CEDE {{app_name}} rp2 ok"
