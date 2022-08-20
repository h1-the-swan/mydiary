import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Table, TableColumnType } from "antd";
import {
  PocketArticleRead,
  PocketStatusEnum,
  TagRead,
  useReadPocketArticles,
  useReadTags,
} from "../api";

export default function PocketArticlesTable() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tagFilter = searchParams.get("tags") || "";
  const dateMinFilter = searchParams.get("dateMin") || "";
  const dateMaxFilter = searchParams.get("dateMax") || "";
  const { data: articles, isLoading } = useReadPocketArticles(
    {
      limit: 500,
      tags: tagFilter,
      dateMin: dateMinFilter,
      dateMax: dateMaxFilter,
    },
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
        <span>
          <a
            href={`https://getpocket.com/read/${record.id}`}
            target="_blank"
            rel="noreferrer"
          >
            {value}
          </a>
          {record.favorite ? "❤️" : null}
        </span>
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
      sorter: (a, b) => a.resolved_title.localeCompare(b.resolved_title),
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
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: PocketStatusEnum) => {
        if (status === 0) {
          return "unread";
        } else if (status === 1) {
          return "archived";
        } else if (status === 2) {
          return "SHOULD_BE_DELETED";
        }
      },
      sorter: (a, b) => a.status - b.status,
      filters: [
        {
          text: "unread",
          value: 0,
        },
        {
          text: "archived",
          value: 1,
        },
        {
          text: "SHOULD_BE_DELETED",
          value: 2,
        },
      ],
      onFilter: (value, record: PocketArticleRead) => record.status === value,
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
