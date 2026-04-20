<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:template match="/">
    <html>
      <body>

        <h2>OEM Driver Version and Status Verification Tool - Ver 2.5.13</h2>
        <div>
          <h3>Device Information</h3>
          <table border="1">
            <xsl:for-each select="Results/DeviceInfo">
              <tr>
                <td> OS Ver String: <xsl:value-of select="OSVerString" />
                </td>
              </tr>
              <tr>
                <td> OS Version: <xsl:value-of select="OS" />
                </td>
              </tr>
              <tr>
                <td> KBs Installed: <xsl:value-of select="HotFixes" />
                </td>
              </tr>
              <tr>
                <td> ComputerName: <xsl:value-of select="ComputerName" />
                </td>
              </tr>
              <tr>
                <td> System SKU: <xsl:value-of select="SystemSKU" />
                </td>
              </tr>
              <tr>
                <td> Image Number: <xsl:value-of select="BuildImage" />
                </td>
              </tr>
              <tr>
                <td> Image Product Name: <xsl:value-of select="ImageProductName" />
                </td>
              </tr>
              <tr>
                <td> Image WIM Name: <xsl:value-of select="ImageName" />
                </td>
              </tr>
              <tr>
                <td> Iteration: <xsl:value-of select="Iteration" />
                </td>
              </tr>
              <tr>
                <td> RailCar ID, Name: <xsl:value-of select="RailCarID" />, <xsl:value-of
                    select="RailCarName" />
                </td>
              </tr>
            </xsl:for-each>
          </table>
        </div>

        <div>
          <h3>FIRMWARE</h3>
          <table border="1">
            <tr bgcolor="#8FBC8F">
              <th>Inf File Path</th>
              <th>Device Name</th>
              <th>Status Code</th>
              <th>Expected Version</th>
              <th>Installed Version</th>
              <th>Match Status</th>
              <th>Rollback</th>
              <th>Expected Driver</th>
              <th>Installed Driver</th>
              <th>Signing Type</th>
            </tr>

            <xsl:for-each select="Results/Result">
              <xsl:sort select="DriverMatchStatus" order="ascending" />
            <xsl:sort select="StatusCode"
                order="descending" />
            <xsl:sort select="InfFilePath" order="descending" />
            <xsl:choose>
                <xsl:when test="DriverType = 'Firmware'">
                  <tr>
                    <xsl:choose>
                      <xsl:when test="contains(InfFilePath, 'SurfaceNullCapsule')">
                        <td bgcolor="#FFFF00">
                          <xsl:element name="a">
                            <xsl:attribute name="href">
                              <xsl:value-of select="InfFilePath" />
                            </xsl:attribute>
                        <xsl:value-of
                              select="InfFilePath" />
                          </xsl:element>
                        </td>
                      </xsl:when>
                      <xsl:when test="InfFilePath = 'NA'">
                        <td bgcolor="#99CCCC">
                        </td>
                      </xsl:when>
                      <xsl:when test="contains(InfFilePath, '\V2_')">
                        <td bgcolor="#CDB3FF">
                          <xsl:element name="a">
                            <xsl:attribute name="href">
                              <xsl:value-of select="InfFilePath" />
                            </xsl:attribute>
                        <xsl:value-of
                              select="InfFilePath" />
                          </xsl:element>
                        </td>
                      </xsl:when>

                      <xsl:otherwise>
                        <td>
                          <xsl:element name="a">
                            <xsl:attribute name="href">
                              <xsl:value-of select="InfFilePath" />
                            </xsl:attribute>
                        <xsl:value-of
                              select="InfFilePath" />
                          </xsl:element>
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <td>
                      <xsl:value-of select="DeviceName" />
                    </td>

                    <xsl:choose>
                      <xsl:when test="StatusCode = '0'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="StatusCode" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="StatusCode" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>


                    <xsl:choose>
                      <xsl:when test="DriverVersionInInfFile = 'NA, NA'">
                        <td bgcolor="#99CCCC">
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'Driver Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF FirmwareVersion mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'NULL capsule, unable to get version'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="contains(DriverMatchStatus, 'Factory Null Capsule')">
                        <td bgcolor="#FFD18C">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'Unexpected Version'">
                        <td bgcolor="Yellow">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FFFFFF">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>


                    <xsl:choose>
                      <xsl:when test="DriverMatchStatus = 'Driver Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF FirmwareVersion mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'NULL capsule, unable to get version'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:when test="contains(DriverMatchStatus, 'Factory Null Capsule')">
                        <td bgcolor="#FFD18C">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FFFFFF">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="DriverMatchStatus = 'Verified'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF match Not Found'">
                        <td bgcolor="#FFFF00" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'NA'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:when test="contains(DriverMatchStatus, 'Factory Null Capsule')">
                        <td bgcolor="#FFD18C" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="Rollback = 'False'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="Rollback" />
                        </td>
                      </xsl:when>
                      <xsl:when test="Rollback = 'True'">
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="Rollback" />
                        </td>
                      </xsl:when>
                      <xsl:when test="Rollback = 'NA'">
                        <td bgcolor="#Yellow" style="text-align:center;">
                          <xsl:value-of select="Rollback" />
                        </td>
                      </xsl:when>
                      <xsl:when test="Rollback = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="Rollback" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="ExpectedSigning = 'WHQL'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'OEMUEFI'">
                        <td bgcolor="Aqua" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'AtTestation'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'NA'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="InstalledSigning = 'WHQL'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'OEMUEFI'">
                        <td bgcolor="Aqua" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'AtTestation'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="not (SigAlgo)">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="SigAlgo = 'Pass'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="(SigAlgo = 'Fail SHA0') or (SigAlgo = 'Fail SHA1')">
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="SigAlgo = ''">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>
                  </tr>
                </xsl:when>
              </xsl:choose>
            </xsl:for-each>
          </table>
        </div>

        <div>
          <h3>DRIVERS</h3>
          <table border="1">
            <tr bgcolor="#8FBC8F">
              <th>Inf File Path</th>
              <th>Device Name</th>
              <th>Status Code</th>
              <th>Expected Version</th>
              <th>Installed Version</th>
              <th>Match Status</th>
              <th>Expected Driver</th>
              <th>Installed Driver</th>
              <th>Signing Type</th>
            </tr>

            <xsl:for-each select="Results/Result">
              <xsl:sort select="DriverMatchStatus" order="ascending" />
            <xsl:sort select="StatusCode"
                order="descending" />
            <xsl:sort select="InfFilePath" order="descending" />
            <xsl:choose>
                <xsl:when test="DriverType != 'Firmware'">
                  <tr>
                    <xsl:choose>
                      <xsl:when test="InfFilePath = 'NA'">
                        <td bgcolor="#99CCCC">
                        </td>
                      </xsl:when>
                      <xsl:when test="contains(InfFilePath, '\V2_')">
                        <td bgcolor="#CDB3FF">
                          <xsl:element name="a">
                            <xsl:attribute name="href">
                              <xsl:value-of select="InfFilePath" />
                            </xsl:attribute>
                        <xsl:value-of
                              select="InfFilePath" />
                          </xsl:element>
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td>
                          <xsl:element name="a">
                            <xsl:attribute name="href">
                              <xsl:value-of select="InfFilePath" />
                            </xsl:attribute>
                        <xsl:value-of
                              select="InfFilePath" />
                          </xsl:element>
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <td>
                      <xsl:value-of select="DeviceName" />
                    </td>

                    <xsl:choose>
                      <xsl:when test="StatusCode = '0'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="StatusCode" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="StatusCode" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="DriverVersionInInfFile = 'NA, NA'">
                        <td bgcolor="#99CCCC">
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'Driver Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF Hash Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'Unexpected Version'">
                        <td bgcolor="Yellow">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:when test="SysFileMatchStatus = 'Sys Version Mismatch'">
                        <td bgcolor="#FFFF00">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FFFFFF">
                          <xsl:value-of select="DriverVersionInInfFile" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="DriverMatchStatus = 'Driver Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF Hash Mismatch'">
                        <td bgcolor="#FF0000">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FFFFFF">
                          <xsl:value-of select="DriverVersionInSystem" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>
                    <xsl:choose>
                      <xsl:when test="DriverMatchStatus = 'Verified'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'INF match Not Found'">
                        <td bgcolor="#FFFF00" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'N/A'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:when test="DriverMatchStatus = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="DriverMatchStatus" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="ExpectedSigning = 'WHQL'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'AtTestation'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'N/A'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:when test="ExpectedSigning = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="ExpectedSigning" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="InstalledSigning = 'WHQL'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'OEMUEFI'">
                        <td bgcolor="Aqua" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'AtTestation'">
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:when>
                      <xsl:when test="InstalledSigning = 'ignore'">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="Yellow" style="text-align:center;">
                          <xsl:value-of select="InstalledSigning" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                    <xsl:choose>
                      <xsl:when test="not (SigAlgo)">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="SigAlgo = 'Pass'">
                        <td bgcolor="#7CFC00" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="(SigAlgo = 'Fail SHA0') or (SigAlgo = 'Fail SHA1')">
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:when test="SigAlgo = ''">
                        <td bgcolor="#99CCCC" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:when>
                      <xsl:otherwise>
                        <td bgcolor="#FF0000" style="text-align:center;">
                          <xsl:value-of select="SigAlgo" />
                        </td>
                      </xsl:otherwise>
                    </xsl:choose>

                  </tr>

                </xsl:when>
              </xsl:choose>
            </xsl:for-each>
          </table>
        </div>


        <div>
          <h3>EXTENSION DRIVERS</h3>
          <table border="1">
            <tr bgcolor="#8FBC8F">
              <th>Expected INF</th>
              <th>Device Name</th>
              <th>Version Expected</th>
              <th>Version Installed</th>
              <th>Match Status</th>
              <th>Expected Driver</th>
              <th>Installed Driver</th>
              <th>Signing Type</th>
            </tr>
            <xsl:for-each select="Results/ExtensionDriver">
              <xsl:sort select="ExtensionExpectedPath" order="descending" />
              <tr>
                <xsl:choose>
                  <xsl:when test="contains(ExtensionExpectedPath, '\V2_')">
                    <td bgcolor="#CDB3FF">
                      <xsl:value-of select="ExtensionExpectedPath" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td>
                      <xsl:value-of select="ExtensionExpectedPath" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <td>
                  <xsl:value-of select="DeviceName" />
                </td>
                <td>
                  <xsl:value-of select="DriverVersionExpected" />
                </td>
                <td>
                  <xsl:value-of select="DriverVersionInInfSystem" />
                </td>

                <xsl:choose>
                  <xsl:when test="DriverMatchStatus = 'Verified'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="DriverMatchStatus" />
                    </td>
                  </xsl:when>
                  <xsl:when test="DriverMatchStatus = 'NotMatched'">
                    <td bgcolor="Yellow" style="text-align:center;">
                      <xsl:value-of select="DriverMatchStatus" />
                    </td>
                  </xsl:when>
                  <xsl:when test="DriverMatchStatus = 'INF Hash Mismatch'">
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="DriverMatchStatus" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="#FFFFFF" style="text-align:center;">
                      <xsl:value-of select="DriverMatchStatus" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <xsl:choose>
                  <xsl:when test="ExpectedSigning = 'WHQL'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="ExpectedSigning" />
                    </td>
                  </xsl:when>
                  <xsl:when test="ExpectedSigning = 'OEMUEFI'">
                    <td bgcolor="Aqua" style="text-align:center;">
                      <xsl:value-of select="ExpectedSigning" />
                    </td>
                  </xsl:when>
                  <xsl:when test="ExpectedSigning = 'TestSigned'">
                    <td bgcolor="Red" style="text-align:center;">
                      <xsl:value-of select="ExpectedSigning" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="Yellow" style="text-align:center;">
                      <xsl:value-of select="ExpectedSigning" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <xsl:choose>
                  <xsl:when test="InstalledSigning = 'WHQL'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="InstalledSigning" />
                    </td>
                  </xsl:when>
                  <xsl:when test="InstalledSigning = 'OEMUEFI'">
                    <td bgcolor="Aqua" style="text-align:center;">
                      <xsl:value-of select="InstalledSigning" />
                    </td>
                  </xsl:when>
                  <xsl:when test="InstalledSigning = 'TestSigned'">
                    <td bgcolor="Red" style="text-align:center;">
                      <xsl:value-of select="InstalledSigning" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="Yellow" style="text-align:center;">
                      <xsl:value-of select="InstalledSigning" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>
                <xsl:choose>
                  <xsl:when test="not (SigAlgo)">
                    <td bgcolor="#99CCCC" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="SigAlgo = 'Pass'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="(SigAlgo = 'Fail SHA0') or (SigAlgo = 'Fail SHA1')">
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="SigAlgo = ''">
                    <td bgcolor="#99CCCC" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>
              </tr>
            </xsl:for-each>
          </table>
        </div>


        <div>
          <h3>OTHER INFs</h3>
          <table border="1">
            <tr bgcolor="#8FBC8F">
              <th>INFS NOT Installed on a Device</th>
              <th>Rollback</th>
              <th>Signed</th>
              <th>Signing Type</th>
            </tr>
            <xsl:for-each select="Results/NotFound">
              <xsl:sort select="NotInstalled" order="descending" />
              <tr>
                <xsl:choose>
                  <xsl:when test="contains(NotInstalled, 'SurfaceNullCapsule')">
                    <td bgcolor="#FFFF00">
                      <xsl:value-of select="NotInstalled" />
                    </td>
                  </xsl:when>
                  <xsl:when test="contains(NotInstalled, '\V2_')">
                    <td bgcolor="#CDB3FF">
                      <xsl:value-of select="NotInstalled" />
                    </td>
                  </xsl:when>

                  <xsl:otherwise>
                    <td>
                      <xsl:value-of select="NotInstalled" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <xsl:choose>
                  <xsl:when test="Rollback = 'False'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="Rollback" />
                    </td>
                  </xsl:when>
                  <xsl:when test="Rollback = 'True'">
                    <td bgcolor="Red" style="text-align:center;">
                      <xsl:value-of select="Rollback" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="Rollback" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <xsl:choose>
                  <xsl:when test="Signed = 'WHQL'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="Signed" />
                    </td>
                  </xsl:when>
                  <xsl:when test="Signed = 'OEMUEFI'">
                    <td bgcolor="Aqua" style="text-align:center;">
                      <xsl:value-of select="Signed" />
                    </td>
                  </xsl:when>
                  <xsl:when test="Signed = 'TestSigned'">
                    <td bgcolor="Yellow" style="text-align:center;">
                      <xsl:value-of select="Signed" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="Yellow" style="text-align:center;">
                      <xsl:value-of select="Signed" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>

                <xsl:choose>
                  <xsl:when test="not (SigAlgo)">
                    <td bgcolor="#99CCCC" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="SigAlgo = 'Pass'">
                    <td bgcolor="#7CFC00" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="(SigAlgo = 'Fail SHA0') or (SigAlgo = 'Fail SHA1')">
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:when test="SigAlgo = ''">
                    <td bgcolor="#99CCCC" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:when>
                  <xsl:otherwise>
                    <td bgcolor="#FF0000" style="text-align:center;">
                      <xsl:value-of select="SigAlgo" />
                    </td>
                  </xsl:otherwise>
                </xsl:choose>
              </tr>
            </xsl:for-each>
          </table>
        </div>


        <div>
          <h3> </h3>
          <table border="1">
            <tr bgcolor="#8FBC8F">
              <th>Excluded Devices</th>
            </tr>
            <xsl:for-each select="Results/Excluded">
              <tr>
                <td>
                  <xsl:value-of select="ExcludedDevice" />
                </td>
              </tr>
            </xsl:for-each>
          </table>
        </div>


      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>