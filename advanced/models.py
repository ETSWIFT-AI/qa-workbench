"""Randomly initialized CNN, GRU, byte Transformer and MLP with late fusion.
No pretrained model, tokenizer, embedding or download is used.
"""
import torch
from torch import nn

class WebsiteNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn=nn.Sequential(nn.Conv2d(3,12,5,stride=2,padding=2),nn.ReLU(),nn.Conv2d(12,24,3,stride=2,padding=1),nn.ReLU(),nn.Conv2d(24,32,3,stride=2,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d(1),nn.Flatten())
        self.rnn=nn.GRU(6,32,batch_first=True)
        self.tokens=nn.Embedding(257,32,padding_idx=0)
        self.position=nn.Parameter(torch.randn(1,256,32)*.02)
        self.transformer=nn.TransformerEncoder(nn.TransformerEncoderLayer(32,4,64,dropout=.1,batch_first=True),num_layers=2,enable_nested_tensor=False)
        # TransformerEncoder clones initial layers; explicitly randomize each layer independently.
        for layer in self.transformer.layers:
            for name,param in layer.named_parameters():
                if param.dim()>1: nn.init.xavier_uniform_(param)
        self.mlp=nn.Sequential(nn.Linear(16,32),nn.ReLU(),nn.Linear(32,32),nn.ReLU())
        self.fusion=nn.Sequential(nn.Linear(128,64),nn.ReLU(),nn.Dropout(.1),nn.Linear(64,2))

    def forward(self,image,tokens,events,event_lengths,features):
        vision=self.cnn(image)
        packed=nn.utils.rnn.pack_padded_sequence(events,event_lengths.cpu(),batch_first=True,enforce_sorted=False)
        _,hidden=self.rnn(packed)
        padding=tokens.eq(0)
        text=self.transformer(self.tokens(tokens)+self.position,src_key_padding_mask=padding)
        mask=(~padding).unsqueeze(-1)
        text=(text*mask).sum(1)/mask.sum(1).clamp(min=1)
        return self.fusion(torch.cat([vision,hidden[-1],text,self.mlp(features)],dim=1))
