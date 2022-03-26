import React from "react";
import { Table, TableColumnType } from "antd";
import { PocketArticleRead, useReadPocketArticles, useReadTags } from "../api";

export default function PocketArticlesTable() {
  const { data: articles, isLoading } = useReadPocketArticles(
    { limit: 500 },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
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
  ];
  return isLoading ? (
    <span>Loading...</span>
  ) : (
    <Table dataSource={articles} columns={columns} />
  );
}
