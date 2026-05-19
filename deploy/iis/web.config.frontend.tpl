<?xml version="1.0" encoding="UTF-8"?>
<!--
  Web.config for the public-facing Next.js site.

  Octopus substitutes #{...} tokens BEFORE this file lands on disk.
  After substitution, this file is dropped into the frontend physical path
  by deploy-prod.ps1.

  Topology recap (see deploy/iis/README.md):
    - This site is bound externally on *:443.
    - HttpPlatformHandler launches `node server.js` from the Next.js
      standalone build on a private loopback port.
    - URL Rewrite peels off /api/* and /static/* and ARR-proxies them
      to the backend site bound to 127.0.0.1:#{BackendPort}, so the browser
      never crosses an origin.
-->
<configuration>
  <system.webServer>

    <handlers>
      <!-- Single catch-all handler: everything not matched by a rewrite rule
           below goes to the Node process. -->
      <add name="httpPlatformHandler"
           path="*"
           verb="*"
           modules="httpPlatformHandler"
           resourceType="Unspecified" />
    </handlers>

    <httpPlatform processPath="#{NodeExePath}"
                  arguments=".\server.js"
                  stdoutLogEnabled="true"
                  stdoutLogFile=".\logs\node-stdout"
                  startupTimeLimit="60"
                  requestTimeout="00:04:00"
                  forwardWindowsAuthToken="false">
      <environmentVariables>
        <environmentVariable name="PORT"             value="%HTTP_PLATFORM_PORT%" />
        <environmentVariable name="HOSTNAME"         value="127.0.0.1" />
        <environmentVariable name="NODE_ENV"         value="production" />
        <!-- Bypassed in prod because URL Rewrite below catches /api/* before
             Node sees it; kept here for parity with dev/docker. -->
        <environmentVariable name="API_INTERNAL_URL" value="http://127.0.0.1:#{BackendPort}" />
      </environmentVariables>
    </httpPlatform>

    <rewrite>
      <rules>
        <!-- Plain HTTP requests get 301 redirected to HTTPS. The site has
             both *:80 and *:443 bindings so this rule fires only on the
             cleartext port. {HTTPS} is set by IIS automatically. -->
        <rule name="HttpsRedirect" stopProcessing="true">
          <match url=".*" />
          <conditions>
            <add input="{HTTPS}" pattern="^OFF$" />
          </conditions>
          <action type="Redirect"
                  url="https://{HTTP_HOST}/{R:0}"
                  redirectType="Permanent" />
        </rule>
        <!-- IMPORTANT: URL Rewrite runs in the IIS pipeline BEFORE the
             httpPlatformHandler fires, so these proxy rules win and the
             request never reaches Node. Order matters: most-specific first. -->
        <rule name="ProxyAPI" stopProcessing="true">
          <match url="^api/(.*)$" />
          <action type="Rewrite"
                  url="http://127.0.0.1:#{BackendPort}/api/{R:1}"
                  logRewrittenUrl="true" />
        </rule>
        <rule name="ProxyStatic" stopProcessing="true">
          <match url="^static/(.*)$" />
          <action type="Rewrite"
                  url="http://127.0.0.1:#{BackendPort}/static/{R:1}"
                  logRewrittenUrl="true" />
        </rule>
      </rules>
    </rewrite>

    <!--
      NOTE: previously included a <serverVariables> block on the ProxyAPI
      rule (setting X-Forwarded-Proto / X-Forwarded-Host) plus a top-level
      <serverRuntime alternateHostName=""/>. Both are locked by default at
      applicationHost.config level (overrideModeDefault="Deny") and produce
      HTTP 500.19 when used in a site-level Web.config without an explicit
      unlock. They are not required for the same-origin proxy to work.
      If/when forwarded headers are needed, unlock at the server level with:
        appcmd.exe unlock config /section:system.webServer/rewrite/allowedServerVariables
      and add the names to a server-level <allowedServerVariables> section.
    -->

    <!-- Match backend's 10 MB upload cap (Flask MAX_CONTENT_LENGTH). -->
    <security>
      <requestFiltering>
        <requestLimits maxAllowedContentLength="10485760" />
      </requestFiltering>
    </security>

    <!-- Standard HSTS / clickjacking headers. -->
    <httpProtocol>
      <customHeaders>
        <add name="Strict-Transport-Security" value="max-age=31536000; includeSubDomains" />
        <add name="X-Content-Type-Options"    value="nosniff" />
        <add name="X-Frame-Options"           value="SAMEORIGIN" />
      </customHeaders>
    </httpProtocol>

  </system.webServer>
</configuration>
