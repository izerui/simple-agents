package com.simpleagents.client;

import com.google.gson.Gson;
import com.google.gson.annotations.SerializedName;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Base64;
import java.util.Map;

/**
 * 文件类型支持:
 * - 本地文件路径: "path/to/file.pdf" 或 Path 对象
 * - URL: "https://example.com/file.pdf"
 * - 字典格式: {"type": "file", "data": "...", "metadata": {"filename": "..."}}
 *
 * 使用方式:
 * <pre>
 * // 本地文件
 * FileType file = FileType.fromPath("path/to/file.pdf");
 *
 * // URL
 * FileType file = FileType.fromUrl("https://example.com/file.pdf");
 *
 * // 字典格式
 * FileType file = FileType.fromMap(Map.of("type", "file", "data", "...", "metadata", Map.of("filename", "test.pdf")));
 * </pre>
 */
public class FileType {

    @SerializedName("type")
    private String type = "file";

    @SerializedName("data")
    private String data;

    @SerializedName("metadata")
    private Map<String, Object> metadata;

    /**
     * 从本地文件路径创建 FileType.
     *
     * @param path 文件路径
     * @return FileType 实例
     */
    public static FileType fromPath(String path) throws IOException {
        return fromPath(Paths.get(path));
    }

    /**
     * 从本地文件路径创建 FileType.
     *
     * @param path Path 对象
     * @return FileType 实例
     */
    public static FileType fromPath(Path path) throws IOException {
        byte[] fileContent = Files.readAllBytes(path);
        String base64Data = Base64.getEncoder().encodeToString(fileContent);

        FileType fileType = new FileType();
        fileType.type = "file";
        fileType.data = base64Data;
        fileType.metadata = Map.of("filename", path.getFileName().toString());
        return fileType;
    }

    /**
     * 从 URL 创建 FileType（下载文件）.
     *
     * @param url 文件 URL
     * @return FileType 实例
     */
    public static FileType fromUrl(String url) throws IOException {
        // 简单实现：假设 url 是 http/https
        java.net.URL fileUrl = new java.net.URL(url);
        try (java.io.InputStream is = fileUrl.openStream()) {
            byte[] content = is.readAllBytes();
            String base64Data = Base64.getEncoder().encodeToString(content);

            // 从 URL 提取文件名
            String filename = url.substring(url.lastIndexOf('/') + 1);
            if (filename.contains("?")) {
                filename = filename.substring(0, filename.indexOf('?'));
            }
            if (filename.isEmpty()) {
                filename = "downloaded_file";
            }

            FileType fileType = new FileType();
            fileType.type = "file";
            fileType.data = base64Data;
            fileType.metadata = Map.of("filename", filename);
            return fileType;
        }
    }

    /**
     * 从 Map 创建 FileType.
     *
     * @param map 字典格式的 Map
     * @return FileType 实例
     */
    @SuppressWarnings("unchecked")
    public static FileType fromMap(Map<String, Object> map) {
        FileType fileType = new FileType();
        fileType.type = (String) map.getOrDefault("type", "file");
        fileType.data = (String) map.get("data");
        fileType.metadata = (Map<String, Object>) map.get("metadata");
        return fileType;
    }

    /**
     * 从 JSON 字符串创建 FileType.
     *
     * @param json JSON 字符串
     * @return FileType 实例
     */
    public static FileType fromJson(String json) {
        return new Gson().fromJson(json, FileType.class);
    }

    // Getters and Setters

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getData() {
        return data;
    }

    public void setData(String data) {
        this.data = data;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }

    /**
     * 转换为 JSON 字符串.
     */
    public String toJson() {
        return new Gson().toJson(this);
    }

    /**
     * 获取文件名.
     */
    public String getFilename() {
        if (metadata != null && metadata.containsKey("filename")) {
            return (String) metadata.get("filename");
        }
        return "unknown";
    }
}
