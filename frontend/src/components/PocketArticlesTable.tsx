import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Table, TableColumnType } from "antd";
import {
  PocketArticleRead,
  TagRead,
  useReadPocketArticles,
  useReadTags,
} from "../api";

export default function PocketArticlesTable() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tagFilter = searchParams.get("tags") || "";
  const { data: articles, isLoading } = useReadPocketArticles(
    { limit: 100, tags: tagFilter },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  useEffect(() => console.log(articles), [articles]);
  // if (!articles) return null;
  const columns: TableColumnType<PocketArticleRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
      render: (value, record) => (
        <a
          href={`https://getpocket.com/read/${record.id}`}
          target="_blank"
          rel="noreferrer"
        >
          {value}
        </a>
      ),
    },
    {
      title: "Title",
      dataIndex: "resolved_title",
      key: "resolved_title",
      render: (value, record) => (
        <a href={record.url} target="_blank" rel="noreferrer">
          {value ? value : "given_title: " + record.given_title}
        </a>
      ),
    },
    {
      title: "Time Added",
      dataIndex: "time_added",
      key: "time_added",
      render: (value: string) => {
        const dt = new Date(value + "Z");
        return dt.toLocaleString();
      },
      sorter: (a, b) =>
        new Date(a.time_added + "Z").getTime() -
        new Date(b.time_added + "Z").getTime(),
    },
    {
      title: "Tags",
      dataIndex: "tags",
      key: "tags",
      render: (tags: TagRead[], record) => {
        const tagNames = tags.map((tag) => tag.name);
        return tagNames.join(", ");
      },
    },
  ];
  return isLoading ? (
    <span>Loading...</span>
  ) : (
    <Table
      dataSource={articles}
      columns={columns}
      pagination={{ pageSize: 100 }}
    />
  );
}
