/*
 * Copyright 2016 Mobicage NV
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * @@license_version:1.1@@
 */
package com.mobicage.rogerthat.branding;

import java.awt.image.BufferedImage;
import java.io.Writer;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.xhtmlrenderer.simple.Graphics2DRenderer;

@SuppressWarnings("serial")
public class RenderServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws javax.servlet.ServletException,
        java.io.IOException {
        String url = req.getParameter("url");
        BufferedImage buff = null;
        buff = Graphics2DRenderer.renderToImageAutoSize(url, 320);
        int height_320 = buff.getHeight();
        buff = Graphics2DRenderer.renderToImageAutoSize(url, 640);
        int height_640 = buff.getHeight();
        Writer w = resp.getWriter();
        w.write("[320,");
        w.write(height_320 + "");
        w.write(",640,");
        w.write(height_640 + "");
        w.write("]");
        resp.setContentType("application/json");
    }
}