<?xml version="1.0" encoding="UTF-8"?>
<!--
  Web.config for the loopback-only Flask backend site.

  Octopus substitutes the #{...} placeholders BEFORE this file lands on disk.

  This site is bound to 127.0.0.1:#{BackendPort} so it is unreachable from
  outside the box; the public frontend site ARR-proxies /api/ and /static/
  here over the loopback. See the <httpPlatform> block below for the exact
  waitress invocation.

  NOTE: XML forbids the sequence of two consecutive hyphens anywhere inside
  a comment. Do not paste shell flags into comments (a leading double-hyphen
  flag will break IIS config parsing with HTTP 500.19).
-->
<configuration>
  <system.webServer>

    <handlers>
      <add name="httpPlatformHandler"
           path="*"
           verb="*"
           modules="httpPlatformHandler"
           resourceType="Unspecified" />
    </handlers>

    <!-- venv interpreter is set up by deploy-prod.ps1 at <DEPLOY_ROOT>\backend\venv. -->
    <httpPlatform processPath="#{BackendPythonExe}"
                  arguments="-m waitress --listen=127.0.0.1:%HTTP_PLATFORM_PORT% --threads=8 app:app"
                  stdoutLogEnabled="true"
                  stdoutLogFile=".\logs\waitress-stdout"
                  startupTimeLimit="60"
                  requestTimeout="00:04:00"
                  forwardWindowsAuthToken="false">
      <environmentVariables>
        <!-- Flask runtime -->
        <environmentVariable name="FLASK_ENV"               value="production" />
        <environmentVariable name="FLASK_DEBUG"             value="0" />
        <environmentVariable name="PORT"                    value="%HTTP_PLATFORM_PORT%" />

        <!-- Same-origin: browser only ever sees the frontend host, so we
             restrict CORS to that. Octopus injects the public host. -->
        <environmentVariable name="CORS_ALLOWED_ORIGINS"    value="https://#{SiteHostname}" />

        <!-- Storage paths (deploy-prod.ps1 creates these dirs). -->
        <environmentVariable name="UPLOAD_DIR"              value="#{DeployRoot}\backend\uploads" />
        <environmentVariable name="DATA_DIR"                value="#{DeployRoot}\backend\database" />
        <environmentVariable name="TEMP_UPLOAD_PATH"        value="#{DeployRoot}\backend\data\uploads" />
        <environmentVariable name="SESSION_STORAGE_PATH"    value="#{DeployRoot}\backend\data\sessions.json" />

        <!-- Secrets — injected by Octopus from its sensitive-variable store. -->
        <environmentVariable name="AZURE_OPENAI_ENDPOINT"   value="#{AzureOpenAiEndpoint}" />
        <environmentVariable name="AZURE_OPENAI_API_KEY"    value="#{AzureOpenAiApiKey}" />
        <environmentVariable name="AZURE_OPENAI_DEPLOYMENT" value="#{AzureOpenAiDeployment}" />

        <!-- Optional DB string. Leave the Octopus variable blank if not used. -->
        <environmentVariable name="DATABASE_URL"            value="#{DatabaseUrl}" />
      </environmentVariables>
    </httpPlatform>

    <!-- 10 MB upload cap matches Flask MAX_CONTENT_LENGTH in app.py. -->
    <security>
      <requestFiltering>
        <requestLimits maxAllowedContentLength="10485760" />
      </requestFiltering>
    </security>

    <!-- This site is loopback-only; no caching headers needed beyond defaults. -->

  </system.webServer>
</configuration>
